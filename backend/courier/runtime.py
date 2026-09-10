"""Application singleton and dashboard protocol. One owner of physical game input."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from backend.config import get_config, update_config, refresh_env_key
from backend.courier.adapters import GaminiAdapter, GeminiModel
from backend.courier.engine import Agent
from backend.courier.storage import Store, now

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PORT = int(os.environ.get("COURIER_DASHBOARD_PORT", "3000"))
if not 1024 <= DASHBOARD_PORT <= 65535:
    raise ValueError("COURIER_DASHBOARD_PORT must be between 1024 and 65535")
ALLOWED_ORIGINS = {f"http://localhost:{DASHBOARD_PORT}", f"http://127.0.0.1:{DASHBOARD_PORT}",
                   "http://localhost:8000", "http://127.0.0.1:8000"}
router = APIRouter()
runtime = None


class JsonLog(logging.Formatter):
    def format(self, record):
        return json.dumps({"timestamp": now(), "level": record.levelname,
            "event": record.getMessage(), "data": getattr(record, "event_data", {})}, ensure_ascii=False, default=str)


class Runtime:
    def __init__(self, path=None, io=None, model=None):
        self.store = Store(path or Path(os.environ.get("COURIER_DATA_DIR", ROOT / "data")) / "courier.sqlite3")
        update_config(self.store.load_settings())
        self.clients = set()
        self.lock = asyncio.Lock()
        self.stop_pending = 0
        self.agent = Agent(self.store, io or GaminiAdapter(), model or GeminiModel(), get_config, self.broadcast)

    async def broadcast(self, snapshot):
        async def send(ws):
            try:
                await asyncio.wait_for(ws.send_json({"type": "agent_status", "data": snapshot}), 0.5)
            except Exception:
                self.clients.discard(ws)
        await asyncio.gather(*(send(ws) for ws in list(self.clients)))

    async def configure(self, updates):
        if not isinstance(updates, dict):
            raise ValueError("Configuration must be an object")
        unknown = set(updates) - set(type(get_config()).model_fields)
        if unknown:
            raise ValueError("Unknown configuration field")
        # Validate first, then stop the old target before applying any control changes.
        type(get_config()).model_validate({**get_config().model_dump(), **updates})
        if self.agent.state.status == "running":
            await self.agent.halt("paused")
        config = update_config(updates)
        self.store.save_settings(config.model_dump())

    async def command(self, command, data=None):
        if not isinstance(command, str):
            raise ValueError("Command must be a string")
        # Interrupt latch is set before waiting for any dashboard/command lock.
        if command in {"pause", "stop", "emergency_stop"}:
            self.agent.interrupt()
            self.stop_pending += 1
        try:
            async with self.lock:
                await self._locked_command(command, data)
        finally:
            if command in {"pause", "stop", "emergency_stop"}:
                self.stop_pending -= 1

    async def _locked_command(self, command, data):
        if command in {"start", "resume"}:
            if self.stop_pending:
                return
            refresh_env_key()
            await self.agent.start()
        elif command in {"pause", "stop", "emergency_stop"}:
            await self.agent.halt({"pause": "paused", "stop": "stopped", "emergency_stop": "emergency_stopped"}[command])
        elif command == "answer_help":
            if not isinstance(data, dict) or not isinstance(data.get("answer"), str):
                raise ValueError("A help request ID and text answer are required")
            should_resume = self.agent.state.status == "need_help"
            await self.agent.answer_help(data.get("request_id"), data["answer"], resume=False)
            if should_resume and not self.stop_pending:
                refresh_env_key()
                await self.agent.start()
        elif command == "config":
            await self.configure(data)
        else:
            raise ValueError("Unknown command")

    async def close(self):
        # A pending help request survives shutdown. Running sessions restore paused.
        status = self.agent.state.status if self.agent.state.status != "running" else "paused"
        await self.agent.halt(status)
        self.store.close()


def initialize():
    global runtime
    runtime = Runtime()
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    handler = RotatingFileHandler(log_dir / "courier.jsonl", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(JsonLog())
    logger = logging.getLogger("courier")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return handler


@router.get("/api/agent/status")
async def status():
    return runtime.agent.snapshot()


@router.get("/api/agent/{collection}")
async def collection(collection: str, limit: int = 20, offset: int = 0, q: str = ""):
    if collection not in {"memories", "skills", "episodes", "human_lessons"}:
        raise HTTPException(404, "Unknown collection")
    if q and collection != "episodes":
        return {"items": runtime.store.retrieve(q[:1000], min(limit, 12))[collection], "search_limit": 12}
    return {"items": runtime.store.recent(collection, limit, offset), "total": runtime.store.counts()[collection]}


async def websocket(ws: WebSocket):
    if ws.headers.get("origin") not in ALLOWED_ORIGINS:
        await ws.close(code=1008)
        return
    await ws.accept()
    runtime.clients.add(ws)
    try:
        await ws.send_json({"type": "agent_status", "data": runtime.agent.snapshot()})
        while True:
            try:
                msg = await ws.receive_json()
                if not isinstance(msg, dict):
                    raise ValueError("Command must be an object")
                await runtime.command(msg.get("command"), msg.get("data"))
                await ws.send_json({"type": "ack", "data": msg.get("command")})
            except (ValueError, ValidationError):
                await ws.send_json({"type": "error", "data": "Invalid command or settings. Check the selected window, API key, field limits and pending help request."})
    except WebSocketDisconnect:
        pass
    finally:
        runtime.clients.discard(ws)
        # Browser reload cannot create another agent; last dashboard loss pauses input.
        if not runtime.clients and runtime.agent.state.status == "running":
            await runtime.command("pause")
