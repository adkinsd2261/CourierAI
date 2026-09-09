"""One Gemini request, zero game inputs. Never prints the API key."""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.config import get_config, refresh_env_key
from backend.courier.adapters import SYSTEM
from backend.courier.models import Observation
from backend.gemini_client import analyze_gameplay

parser = argparse.ArgumentParser()
parser.add_argument("--video", type=Path, help="Optional previously captured game MP4")
args = parser.parse_args()
refresh_env_key()
config = get_config()
if config.gemini_api_key in {"", "your-key-here", "your-actual-key-here"}:
    raise SystemExit("Save GEMINI_API_KEY in .env first.")

async def check():
    video = args.video.read_bytes() if args.video else None
    prompt = "OBSERVE the selected game clip." if video else "Schema connectivity test only: return summary='Connectivity test passed', location='Unknown', no entities or hypotheses."
    result = await analyze_gameplay(video, config, retry_count=0, response_schema=Observation,
        system_prompt=SYSTEM, context_prompt=prompt)
    print("PASS: Gemini returned a locally validated structured observation.")
    print(result.model_dump_json(indent=2))

try:
    asyncio.run(check())
except Exception as exc:
    raise SystemExit(str(exc).replace(config.gemini_api_key, "[REDACTED]")) from None
