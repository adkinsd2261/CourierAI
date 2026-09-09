import pytest
from backend.courier.state import AgentState, Episode, MemoryWrite
from backend.courier.storage import Store


def memory(content="E opens a highlighted door", **kwargs):
    return MemoryWrite(type="mechanic", content=content, tags=["door"], importance=0.8, confidence=0.7, **kwargs)


def test_persistence_and_deduplication(tmp_path):
    path = tmp_path / "courier.sqlite3"
    store = Store(path)
    assert store.add_memory(memory()) == store.add_memory(memory(" E opens a highlighted door "))
    store.add_episode(Episode(summary="Door opened", goal="Exit room", result="success"))
    store.add_human_lesson("Interact key?", "E", {"goal": "Exit room"}, ["controls"])
    store.close()
    restored = Store(path)
    assert restored.counts() == {"memories": 1, "skills": 0, "episodes": 1, "human_lessons": 1}
    assert restored.recent("memories")[0]["confirmation_count"] == 0
    assert restored.recent("human_lessons")[0]["answer"] == "E"
    restored.close()


def test_restoration_keeps_intentions_but_never_runs(tmp_path):
    path = tmp_path / "courier.sqlite3"
    store = Store(path)
    state = AgentState(current_goal="Leave Doc's house", secondary_goals=["Find supplies"],
                       status="running", active_plan=["Find door"], pending_action={"expected_result": "Door opens"})
    store.save_state(state)
    store.save_settings({"gemini_api_key": "SECRET", "game_context": "E to interact"})
    store.close()
    restored = Store(path)
    assert restored.load_state().status == "paused"
    assert restored.load_state().current_goal == state.current_goal
    assert restored.load_state().pending_action == state.pending_action
    assert restored.load_settings() == {"game_context": "E to interact"}
    restored.close()


def test_meaningful_only_and_atomic_rollback(tmp_path):
    store = Store(tmp_path / "db")
    assert store.add_memory(memory().model_copy(update={"importance": 0.1})) is None
    with pytest.raises(RuntimeError):
        with store.atomic():
            store.add_memory(memory())
            raise RuntimeError("simulated checkpoint failure")
    assert store.counts()["memories"] == 0
    with pytest.raises(ValueError):
        store.recent("memories; DROP TABLE memories")
    store.close()
