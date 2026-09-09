import asyncio
import pytest
from backend.courier.engine import Agent
from backend.courier.models import Action, CourierConfig, Decision, Evaluation, Observation, validate_actions
from backend.courier.storage import Store


class FakeIO:
    def __init__(self):
        self.actions = []
        self.captures = 0
        self.released = False
    async def capture(self, config):
        self.captures += 1
        return b"fixture-video"
    async def execute(self, actions, config):
        self.actions += actions
    async def release(self):
        self.released = True
    def interrupt(self): pass
    def arm(self): pass


class FakeModel:
    def __init__(self):
        self.contexts = []
    async def ask(self, schema, phase, context, config, video=None):
        self.contexts.append((phase, context))
        if phase == "observe":
            return Observation(summary="A closed door with an E prompt", location="Doctor's house")
        if phase == "decide":
            return Decision(observation="Door prompt", current_goal="Leave the house",
                reasoning_summary="Interact with the visible door prompt", actions=[Action(action="key_press", key="e")],
                expected_result="The door opens", confidence=0.8)
        if phase == "evaluate":
            return Evaluation(observation="Door opened", outcome="success", evidence="The doorway is now open",
                meaningful_progress=True, confidence=0.9, memory_writes=[{
                    "type": "mechanic", "content": "E opened this highlighted door", "importance": 0.8, "confidence": 0.8}])
        raise AssertionError(phase)


async def discard(_): pass


@pytest.mark.asyncio
async def test_closed_loop_and_restart(tmp_path):
    path = tmp_path / "db"
    store, io, model = Store(path), FakeIO(), FakeModel()
    agent = Agent(store, io, model, lambda: CourierConfig(), discard)
    await agent.step()
    assert io.captures == 2 and io.actions[0].key == "e"
    assert agent.state.pending_action is None
    assert agent.state.statistics["successes"] == 1
    assert store.counts()["memories"] == 1
    store.close()
    store = Store(path)
    restored = Agent(store, FakeIO(), model, lambda: CourierConfig(), discard)
    assert restored.state.current_goal == "Leave the house"
    assert restored.task is None
    store.close()


@pytest.mark.parametrize("payload", [
    {"action": "shell", "command": "calc"},
    {"action": "key_down", "key": "w"},
    {"action": "key_press", "key": "alt"},
    {"action": "key_press", "key": "f12"},
    {"action": "key_press", "key": "backquote"},
    {"action": "wait", "duration": float("nan")},
    {"action": "wait", "duration": 3},
    {"action": "mouse_click", "x": 100, "y": 200},
    {"action": "mouse_click", "bbox": [500, 0, 100, 1000]},
    {"action": "mouse_move", "dx": 999999},
    {"action": "mouse_move"},
])
def test_action_rejection(payload):
    with pytest.raises(ValueError):
        Action.model_validate(payload)


def test_action_config_budgets():
    with pytest.raises(ValueError):
        validate_actions([Action(action="wait", duration=2)], CourierConfig())
    with pytest.raises(ValueError):
        validate_actions([Action(action="wait", duration=0.8)] * 4, CourierConfig())
    with pytest.raises(ValueError):
        validate_actions([Action(action="key_press", key="e")], CourierConfig(allowed_keys=["w"]))


@pytest.mark.asyncio
async def test_cancellation_releases_held_key():
    from backend.courier.adapters import GaminiAdapter
    from backend.input_controller import InputBackend
    recorded = []
    class Recorder(InputBackend):
        async def execute_action(self, action):
            await asyncio.sleep(0.01)
            recorded.append(action.action.value)
    adapter = GaminiAdapter()
    adapter._input = Recorder()
    adapter._window = lambda config, focus=False: {"x": 0, "y": 0, "w": 640, "h": 480}
    task = asyncio.create_task(adapter.execute([Action(action="key_press", key="w", duration=1)], CourierConfig()))
    await asyncio.sleep(0.002)  # cancel while the down event is in flight
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert recorded == ["key_down", "key_up"]
    assert not adapter._held_keys


@pytest.mark.asyncio
async def test_interrupted_attempt_is_not_replayed(tmp_path):
    store, io = Store(tmp_path / "db"), FakeIO()
    agent = Agent(store, io, FakeModel(), lambda: CourierConfig(), discard)
    agent.state.pending_action = {"actions": [{"action": "key_press", "key": "f5"}]}
    await agent.step()
    assert [a.key for a in io.actions] == ["e"]
    assert any(e["result"] == "interrupted" for e in store.recent("episodes"))
    store.close()
