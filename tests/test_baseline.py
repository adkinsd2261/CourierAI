"""Upstream contract tests: no API credentials, capture, or physical input required."""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.game_loop import GameLoop
from backend.models import GameAction, GameActionResponse
from backend.input_controller import InputBackend
from backend.capture import _build_input_args, _output_args


def test_backend_boot_and_read_endpoints(monkeypatch):
    monkeypatch.setattr(main, "_register_emergency_hotkey", lambda: None)
    monkeypatch.setattr(main, "list_windows", lambda: [{"title": "Fixture game", "geometry": None}])
    with TestClient(main.app) as client:
        assert client.get("/api/config").status_code == 200
        assert client.get("/api/windows").json()["windows"][0]["title"] == "Fixture game"


def test_upstream_coordinate_mapping():
    loop = GameLoop(AsyncMock())
    response = GameActionResponse(reasoning="Click menu", actions=[GameAction(action="mouse_click", bbox=[100, 200, 300, 400])])
    loop._scale_actions(response, {"width": 1000, "height": 500, "offset_x": 20, "offset_y": 30})
    assert (response.actions[0].x, response.actions[0].y) == (320, 130)


def test_ffmpeg_contract(monkeypatch):
    monkeypatch.setattr("backend.capture.sys.platform", "win32")
    args = _build_input_args(2, "Fixture game", {"x": 10, "y": 20, "w": 800, "h": 600})
    assert "gdigrab" in args and "800x600" in args
    assert "libx264" in _output_args("fixture.mp4")


@pytest.mark.asyncio
async def test_upstream_input_sequence():
    class Recorder(InputBackend):
        async def execute_action(self, action):
            recorded.append(action)
    recorded = []
    await Recorder().execute_actions([GameAction(action="wait", duration=0)], delay=0)
    assert len(recorded) == 1
