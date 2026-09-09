"""Readiness report; does not expose keys, call Gemini or send game input."""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.config import get_config, refresh_env_key
from backend.window_manager import list_windows

refresh_env_key()
config = get_config()
print(json.dumps({
    "python": sys.version.split()[0],
    "ffmpeg_on_path": bool(shutil.which("ffmpeg")),
    "bundled_ffmpeg_prepared": (Path(sys.executable).parent / "ffmpeg.exe").exists(),
    "gemini_key_configured": config.gemini_api_key not in {"", "your-key-here", "your-actual-key-here"},
    "model": config.model,
    "fallout_windows": [w["title"] for w in list_windows() if "fallout" in w["title"].lower()],
    "frontend_built": (Path(__file__).resolve().parents[1] / "frontend/.next/BUILD_ID").exists(),
}, indent=2))
