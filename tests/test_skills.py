from backend.courier.models import Action, Decision, Evaluation, SkillProposal
from backend.courier.state import Episode, MemoryWrite
from backend.courier.storage import Store


def trial(store, outcome="success"):
    actions = [Action(action="key_press", key="e")]
    decision = Decision(observation="Door", current_goal="Exit", reasoning_summary="Use visible prompt",
        actions=actions, expected_result="Door opens", confidence=0.8)
    evaluation = Evaluation(observation="Door result", outcome=outcome, evidence="Visible doorway change", confidence=0.9)
    eid = store.add_episode(Episode(summary="Tried the door", goal="Exit", result=outcome))
    store.record_trial(eid, decision, evaluation)
    return eid, SkillProposal(name="Open highlighted door", description="Interact with an E door prompt",
        procedure=actions, preconditions=["Highlighted door with E prompt"],
        success_signals=["Doorway opens"], failure_signals=["Door stays closed"])


def test_skill_acquisition_requires_observed_matching_success(tmp_path):
    store = Store(tmp_path / "db")
    failed, proposal = trial(store, "failure")
    assert store.acquire_skill(proposal, failed) is None
    success, proposal = trial(store)
    mismatched = proposal.model_copy(update={"procedure": [Action(action="key_press", key="w")]})
    assert store.acquire_skill(mismatched, success) is None
    skill_id = store.acquire_skill(proposal, success)
    store.acquire_skill(proposal, success)  # reflection sees the same evidence
    skill = store.recent("skills")[0]
    assert skill["success_count"] == 1 and skill["confidence"] == 0.5
    for _ in range(3):
        failed, _ = trial(store, "failure")
        store.feedback("skills", skill_id, failed, "failure")
    assert store.recent("skills")[0]["confidence"] < 0.3
    success2, _ = trial(store)
    store.feedback("skills", skill_id, success2, "success")
    assert store.recent("skills")[0]["confidence"] > 0.3
    store.close()


def test_memory_counterevidence_persists(tmp_path):
    path = tmp_path / "db"
    store = Store(path)
    mid = store.add_memory(MemoryWrite(type="mechanic", content="This door opens with E", confidence=0.8, importance=0.8))
    for eid in range(1, 4):
        store.feedback("memories", mid, eid, "failure")
    store.feedback("memories", mid, 3, "failure")
    store.close()
    store = Store(path)
    item = store.recent("memories")[0]
    assert item["failure_count"] == 3 and item["confidence"] < 0.4
    assert store.retrieve("door")["memories"][0]["id"] == mid
    store.close()
