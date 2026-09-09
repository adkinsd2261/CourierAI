"""Runtime configuration with .env loading and live updates."""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv, dotenv_values

from backend.courier.models import CourierConfig as AppConfig

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

_config = AppConfig(gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
                    model=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"))
_lock = Lock()


def get_config() -> AppConfig:
    with _lock:
        return _config.model_copy()


def refresh_env_key() -> None:
    """Allow the first locally saved key to be picked up without a server restart."""
    if get_config().gemini_api_key in {"", "your-key-here", "your-actual-key-here"}:
        key = dotenv_values(_env_path).get("GEMINI_API_KEY")
        if key and key not in {"your-key-here", "your-actual-key-here"}:
            update_config({"gemini_api_key": key})


def update_config(updates: dict) -> AppConfig:
    global _config
    # Fields that are Optional and can legitimately be set to None
    _nullable_fields = {"target_window"}
    with _lock:
        data = _config.model_dump()
        for k, v in updates.items():
            if v is not None or k in _nullable_fields:
                data[k] = v
        _config = AppConfig(**data)
        return _config.model_copy()
