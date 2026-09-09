from unittest.mock import AsyncMock
import pytest
from backend.courier.escalation import escalation_reason
from backend.courier.models import CourierConfig, Decision
from backend.courier.state import AgentState
from backend.courier.engine import Agent
from backend.courier.storage import Store
from test_agent import FakeIO, FakeModel, discard


def decision(**updates):
    return Decision(observation="Unfamiliar door", current_goal="Open the door", reasoning_summary="Try interacting",
                    expected_result="Door opens", confidence=0.7, **updates)


@pytest.mark.parametrize("field,threshold", [("objective_failures", 4), ("low_confidence_streak", 3), ("no_progress_seconds", 180)])
def test_threshold_boundaries(field, threshold):
    state, config = AgentState(), CourierConfig()
    setattr(state, field, threshold - 1)
    assert escalation_reason(state, decision(), config) is None
    setattr(state, field, threshold)
    assert escalation_reason(state, decision(), config)


def test_unfamiliar_is_not_enough_but_irreversible_ambiguity_is():
    assert escalation_reason(AgentState(), decision(needs_human=True, human_question="What's this?"), CourierConfig()) is None
    assert escalation_reason(AgentState(), decision(irreversible_risk=True,
        plausible_interpretations=["Permanently attack faction", "Only a warning"]), CourierConfig())


@pytest.mark.asyncio
async def test_help_is_durable_answered_once_and_resumes(tmp_path):
    path = tmp_path / "db"
    store, io = Store(path), FakeIO()
    agent = Agent(store, io, FakeModel(), lambda: CourierConfig(), discard)
    agent.state.current_goal = "Open the door"
    agent.state.objective_failures = 4
    assert not await agent.before_action(decision(), {}, CourierConfig())
    rid = agent.state.pending_help["id"]
    assert io.released and not io.actions
    store.close()
    store = Store(path)
    restored = Agent(store, FakeIO(), FakeModel(), lambda: CourierConfig(), discard)
    restored.start = AsyncMock()
    assert restored.state.status == "need_help"
    await restored.answer_help(rid, "Face the handle, then press E")
    restored.start.assert_awaited_once()
    assert store.retrieve("door")["human_lessons"]
    with pytest.raises(ValueError):
        await restored.answer_help(rid, "Duplicate")
    store.close()


@pytest.mark.asyncio
async def test_answer_cannot_override_emergency_stop(tmp_path):
    store = Store(tmp_path / "db")
    agent = Agent(store, FakeIO(), FakeModel(), lambda: CourierConfig(), discard)
    await agent.request_help("stuck")
    await agent.halt("emergency_stopped")
    agent.start = AsyncMock()
    await agent.answer_help(agent.state.pending_help["id"], "Use E")
    agent.start.assert_not_awaited()
    assert agent.state.status == "emergency_stopped"
    store.close()
