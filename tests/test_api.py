from fastapi.testclient import TestClient
from backend import main


def test_shared_agent_help_and_origin_checks(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main, "_register_emergency_hotkey", lambda: None)
    with TestClient(main.app) as client:
        assert client.get("/api/agent/status").json()["state"] == "idle"
        assert client.get("/api/agent/memories").json()["items"] == []
        assert client.post("/api/config", json={"capture_width": 99999}).status_code == 422
        assert client.post("/api/config", headers={"origin": "https://evil.example"}, json={"target_window": "anything"}).status_code == 403
        assert client.post("/api/config", json={"capture_width": 800, "root_instruction": "Explore and survive carefully."}).status_code == 200
        with client.websocket_connect("/ws", headers={"origin": "http://localhost:3000"}) as ws:
            assert ws.receive_json()["type"] == "agent_status"
            ws.send_json({"command": "emergency_stop"})
            message = ws.receive_json()
            assert message["data"]["state"] == "emergency_stopped"
            assert ws.receive_json()["type"] == "ack"
        assert client.get("/api/agent/status").json()["state"] == "emergency_stopped"
    with TestClient(main.app) as client:
        assert client.get("/api/config").json()["capture_width"] == 800
        assert client.get("/api/agent/status").json()["state"] == "emergency_stopped"
