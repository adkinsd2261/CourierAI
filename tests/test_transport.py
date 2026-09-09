from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from backend import gemini_client
from backend.courier.models import CourierConfig, Observation, Decision, Evaluation, Reflection


@pytest.mark.parametrize("schema,payload", [
    (Observation, {"summary": "Closed door"}),
    (Decision, {"observation": "Door", "current_goal": "Exit room", "reasoning_summary": "Test E",
        "expected_result": "Open door", "confidence": 0.7}),
    (Evaluation, {"observation": "Open door", "outcome": "success", "evidence": "Visible opening", "confidence": 0.8}),
    (Reflection, {"summary": "E worked on the door", "evidence_episode_ids": [1]}),
])
async def test_custom_contract_uses_json_schema_and_local_validation(monkeypatch, schema, payload):
    generate = AsyncMock(return_value=SimpleNamespace(parsed=payload, text=None))
    monkeypatch.setattr(gemini_client, "_get_client", lambda _: SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))))
    result = await gemini_client.analyze_gameplay(None, CourierConfig(gemini_api_key="fixture"),
        response_schema=schema, context_prompt="Fixture request", system_prompt="Fixture instruction")
    request = generate.call_args.kwargs
    assert request["config"].response_schema is None
    assert request["config"].response_json_schema["additionalProperties"] is False
    assert request["contents"][0].text == "Fixture request"
    assert isinstance(result, schema)


async def test_invalid_schema_response_is_rejected(monkeypatch):
    generate = AsyncMock(return_value=SimpleNamespace(parsed={"summary": "Door", "shell": "calc"}, text=None))
    monkeypatch.setattr(gemini_client, "_get_client", lambda _: SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))))
    with pytest.raises(RuntimeError):
        await gemini_client.analyze_gameplay(None, CourierConfig(), retry_count=0, response_schema=Observation)


async def test_compact_wire_schema_does_not_relax_action_limits(monkeypatch):
    payload = {"observation": "Door", "current_goal": "Exit room", "reasoning_summary": "Test E",
               "expected_result": "Open door", "confidence": 0.7,
               "actions": [{"action": "key_press", "key": "e", "duration": 30}]}
    generate = AsyncMock(return_value=SimpleNamespace(parsed=payload, text=None))
    monkeypatch.setattr(gemini_client, "_get_client", lambda _: SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))))
    with pytest.raises(RuntimeError):
        await gemini_client.analyze_gameplay(None, CourierConfig(), retry_count=0, response_schema=Decision)
    action = generate.call_args.kwargs["config"].response_json_schema["$defs"]["Action"]
    assert "maximum" not in action["properties"]["duration"]
    assert action["additionalProperties"] is False
    assert action["properties"]["action"]["enum"] == ["key_press", "mouse_move", "mouse_click", "wait"]


async def test_provider_400_not_retried_and_secret_redacted(monkeypatch, caplog):
    class ProviderError(Exception):
        code = 400
    generate = AsyncMock(side_effect=ProviderError("Invalid request: SECRET_KEY"))
    monkeypatch.setattr(gemini_client, "_get_client", lambda _: SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))))
    with pytest.raises(RuntimeError) as exc:
        await gemini_client.analyze_gameplay(None, CourierConfig(gemini_api_key="SECRET_KEY"), response_schema=Observation)
    assert generate.await_count == 1
    assert "SECRET_KEY" not in str(exc.value)
    assert "SECRET_KEY" not in caplog.text
