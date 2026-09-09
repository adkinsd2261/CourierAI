"""Scripted integration fixtures. These never replace live gameplay acceptance."""
import asyncio
from unittest.mock import AsyncMock

from backend.courier.engine import Agent
from backend.courier.models import Action, CourierConfig, Decision, Evaluation, Observation, Reflection, SkillProposal
from backend.courier.storage import Store
from test_agent import FakeIO, discard


class ScriptedGame:
    def __init__(self):
        self.turn = 0
        self.contexts = []
    async def ask(self, schema, phase, context, config, video=None):
        self.contexts.append((phase, context))
        if phase == "observe":
            return Observation(summary="An E prompt on a door", location="Doctor's house", salient_entities=["door"])
        if phase == "decide":
            self.turn += 1
            return Decision(observation="Door", current_goal="Find a route out", reasoning_summary="Try another way to interact",
                expected_result="Door opens", confidence=0.8, actions=[Action(action="key_press", key="e")])
        if phase == "evaluate":
            if self.turn == 1:
                return Evaluation(observation="Door opens", outcome="success", confidence=0.9,
                    evidence="Visible open doorway", meaningful_progress=True,
                    memory_writes=[{"type": "mechanic", "content": "The highlighted door responded to E", "confidence": 0.8, "importance": 0.8}],
                    skill_updates=[SkillProposal(name="Open highlighted door", description="Use the E prompt to open the door",
                        procedure=[Action(action="key_press", key="e")], preconditions=["E prompt on door"],
                        success_signals=["Doorway opens"], failure_signals=["Door remains shut"])])
            return Evaluation(observation="Door stays shut", outcome="failure", confidence=0.9, evidence="Door did not open")
        if phase == "reflect":
            return Reflection(summary="Door interaction worked once but a later attempt failed; check the prompt before repeating.",
                evidence_episode_ids=[context["recent_trials"][0]["episode_id"]])
        raise AssertionError(phase)


async def test_learning_failure_escalation_answer_and_restart(tmp_path):
    path = tmp_path / "db"
    store, model, io = Store(path), ScriptedGame(), FakeIO()
    config = CourierConfig(failure_limit=2, reflection_interval=2)
    agent = Agent(store, io, model, lambda: config, discard)
    await agent.step()
    assert store.counts()["skills"] == store.counts()["memories"] == 1
    await agent.step()
    assert agent.state.statistics["reflections"] == 1
    await agent.step()
    assert agent.state.status == "need_help" and len(io.actions) == 3
    rid = agent.state.pending_help["id"]
    agent.start = AsyncMock()
    await agent.answer_help(rid, "Aim directly at the handle before pressing E.")
    agent.start.assert_awaited_once()
    store.close()
    store = Store(path)
    restored = Agent(store, FakeIO(), model, lambda: config, discard)
    assert restored.state.current_goal == "Find a route out"
    assert restored.state.pending_help is None
    await restored.step()
    latest = [ctx for phase, ctx in model.contexts if phase == "decide"][-1]
    assert latest["retrieved"]["skills"] and latest["retrieved"]["human_lessons"]
    assert "handle" in latest["recent_human_lessons"][0]["answer"]
    store.close()


async def test_emergency_stop_during_answer_wins(tmp_path):
    from backend.courier.runtime import Runtime
    runtime = Runtime(tmp_path / "db", io=FakeIO(), model=ScriptedGame())
    await runtime.agent.request_help("stuck")
    gate, entered = asyncio.Event(), asyncio.Event()
    original = runtime.agent.answer_help
    async def slow_answer(*args, **kwargs):
        entered.set()
        await gate.wait()
        await original(*args, **kwargs)
    runtime.agent.answer_help = slow_answer
    runtime.agent.start = AsyncMock()
    answer = asyncio.create_task(runtime.command("answer_help", {"request_id": runtime.agent.state.pending_help["id"], "answer": "Use E"}))
    await entered.wait()
    stopping = asyncio.create_task(runtime.command("emergency_stop"))
    await asyncio.sleep(0)
    gate.set()
    await asyncio.gather(answer, stopping)
    runtime.agent.start.assert_not_awaited()
    assert runtime.agent.state.status == "emergency_stopped"
    await runtime.close()


def test_failsafe_corner_does_not_prevent_release(monkeypatch):
    from backend import input_windows
    from backend.models import GameAction
    sent = []
    monkeypatch.setattr(input_windows.pydirectinput, "FAILSAFE", True)
    def release(key):
        assert input_windows.pydirectinput.FAILSAFE is False
        sent.append(key)
    monkeypatch.setattr(input_windows.pydirectinput, "keyUp", release)
    input_windows.WindowsInputBackend()._execute_sync(GameAction(action="key_up", key="w"))
    assert sent == ["w"] and input_windows.pydirectinput.FAILSAFE is True
