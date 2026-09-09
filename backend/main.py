"""FastAPI app with REST routes and WebSocket handler."""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from backend.courier import runtime as courier
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.config import get_config, update_config
from backend.window_manager import list_windows

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Emergency stop hotkey state
_emergency_stop_callbacks: list = []


def _fire_emergency_stop() -> None:
    """Invoke all registered emergency stop callbacks."""
    logger.warning("EMERGENCY STOP triggered")
    for cb in _emergency_stop_callbacks:
        try:
            cb()
        except Exception:
            pass


def _register_emergency_hotkey() -> None:
    """Register F12 as global emergency stop hotkey."""
    import threading
    shutdown = threading.Event()

    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes

        def _hotkey_listener():
            user32 = ctypes.windll.user32
            MOD_NONE = 0
            VK_F12 = 0x7B
            HOTKEY_ID = 1

            registered = user32.RegisterHotKey(None, HOTKEY_ID, MOD_NONE, VK_F12)
            if not registered:
                logger.warning("F12 registration unavailable; using global key-state fallback")
            try:
                msg = ctypes.wintypes.MSG()
                was_down = False
                while not shutdown.wait(0.02):
                    if registered:
                        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                            if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:
                                _fire_emergency_stop()
                    else:
                        down = bool(user32.GetAsyncKeyState(VK_F12) & 0x8000)
                        if down and not was_down:
                            _fire_emergency_stop()
                        was_down = down
            finally:
                user32.UnregisterHotKey(None, HOTKEY_ID)

        t = threading.Thread(target=_hotkey_listener, daemon=True)
        t.start()
        return shutdown

    elif sys.platform == "darwin":
        try:
            from Quartz import (
                CGEventMaskBit,
                kCGEventKeyDown,
            )
            from AppKit import NSEvent

            def _macos_key_handler(event):
                # F12 keycode = 0x6F (111)
                if event.keyCode() == 0x6F:
                    _fire_emergency_stop()

            NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                CGEventMaskBit(kCGEventKeyDown),
                _macos_key_handler,
            )
        except ImportError:
            logger.warning("Could not register macOS emergency hotkey (pyobjc not available)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    handler = courier.initialize()
    event_loop = asyncio.get_running_loop()
    def emergency_stop():
        courier.runtime.agent.interrupt()
        asyncio.run_coroutine_threadsafe(courier.runtime.command("emergency_stop"), event_loop)
    _emergency_stop_callbacks.append(emergency_stop)
    hotkey_shutdown = _register_emergency_hotkey()
    try:
        yield
    finally:
        _emergency_stop_callbacks.remove(emergency_stop)
        if hotkey_shutdown:
            hotkey_shutdown.set()
        await courier.runtime.close()
        logging.getLogger("courier").removeHandler(handler)
        handler.close()


app = FastAPI(title="CourierAI", lifespan=lifespan)
app.include_router(courier.router)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])


@app.middleware("http")
async def local_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in courier.ALLOWED_ORIGINS:
        return JSONResponse({"error": "Untrusted dashboard origin"}, status_code=403)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(courier.ALLOWED_ORIGINS),
    allow_methods=["*"],
    allow_headers=["*"],
)


TEMP_DIR = Path(__file__).resolve().parent.parent / "temp"


@app.get("/api/video/{filename}")
async def get_video(filename: str):
    path = TEMP_DIR / filename
    if path.resolve().parent != TEMP_DIR.resolve() or not path.exists() or not path.name.endswith(".mp4"):
        return {"error": "not found"}
    return FileResponse(
        path,
        media_type="video/mp4",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/api/windows")
async def get_windows():
    loop = asyncio.get_event_loop()
    windows = await loop.run_in_executor(None, list_windows)
    return {"windows": windows}


@app.get("/api/config")
async def get_config_endpoint():
    config = get_config()
    data = config.model_dump()
    # Mask API key
    if data["gemini_api_key"]:
        key = data["gemini_api_key"]
        data["gemini_api_key"] = key[:4] + "..." + key[-4:] if len(key) > 8 else "***"
    return data


@app.post("/api/config")
async def update_config_endpoint(updates: dict):
    try:
        async with courier.runtime.lock:
            await courier.runtime.configure(updates)
    except ValueError:
        return JSONResponse({"error": "Invalid configuration values"}, status_code=422)
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await courier.websocket(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
