from backend.courier.state import MemoryWrite
from backend.courier.storage import Store


def test_recall_relevance_lessons_and_hostile_query(tmp_path):
    store = Store(tmp_path / "db")
    door = store.add_memory(MemoryWrite(type="mechanic", content="E opens highlighted doors",
        importance=0.8, confidence=0.8, tags=["door", "interact"]))
    store.add_memory(MemoryWrite(type="person", content="Doc Mitchell lives in Goodsprings",
        importance=0.7, confidence=0.8))
    store.add_human_lesson("How do I open the door?", "Use E while aiming at the door", {}, ["interact"])
    found = store.retrieve('door " OR NOT * ; DROP TABLE memories', 1)
    assert found["memories"][0]["id"] == door
    assert found["human_lessons"][0]["answer"].startswith("Use E")
    assert store.recent("memories")[1]["last_used_at"] is not None
    assert store.retrieve("") == {"memories": [], "skills": [], "human_lessons": []}
    assert store.counts()["memories"] == 2
    store.close()


def test_index_backfills_preexisting_database(tmp_path):
    path = tmp_path / "db"
    store = Store(path)
    store.add_human_lesson("Door key?", "E", {}, ["door"])
    store.db.execute("DELETE FROM recall")
    store.db.execute("PRAGMA user_version=1")
    store.close()
    reopened = Store(path)
    assert reopened.retrieve("door")["human_lessons"][0]["answer"] == "E"
    reopened.close()
