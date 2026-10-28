import os
import tempfile
from datetime import timedelta

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["BANDIT_UPDATE_SECONDS"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import modules  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import BanditDecision  # noqa: E402

LONG_DRAFT = (
    "Our system is really slow. Caching is a good thing.\n\n"
    "The registration service handles a lot of requests during enrollment week and the database becomes the "
    "bottleneck because every page load issues several queries that return the same data for every student.\n\n"
    "We propose adding a read-through cache in front of the course catalog."
)


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c


def login(c, username):
    r = c.post("/api/auth/login", json={"username": username, "password": "password"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def course_and_assignment(c, inst):
    course = c.get("/api/instructor/courses", headers=inst).json()[0]
    a = c.get(f"/api/instructor/courses/{course['id']}/assignments", headers=inst).json()[0]
    return course, a


# ---------------------------------------------------------------- module registry

def test_resolve_layers_and_dependencies():
    cfg, prov = modules.resolve([
        ("course", {"on_demand_feedback": {"cooldown_seconds": 5}}),
        ("assignment", {"on_demand_feedback": {"enabled": False}}),
    ])
    assert cfg["on_demand_feedback"]["cooldown_seconds"] == 5
    assert prov["on_demand_feedback"]["cooldown_seconds"] == "course"
    assert cfg["on_demand_feedback"]["enabled"] is False
    # reward depends on on-demand feedback → forced off
    assert cfg["reward"]["enabled"] is False
    assert prov["reward"]["enabled"] == "dependency:on_demand_feedback"


def test_validate_rejects_unknown_and_out_of_range():
    with pytest.raises(modules.ConfigError):
        modules.validate_overrides({"nope": {"enabled": True}})
    with pytest.raises(modules.ConfigError):
        modules.validate_overrides({"instructor_review": {"sample_size": 50}})
    with pytest.raises(modules.ConfigError):
        modules.validate_overrides({"realtime_feedback": {"presentation": "fireworks"}})


def test_invalid_config_rejected_by_api(client):
    inst = login(client, "drlee")
    course, _ = course_and_assignment(client, inst)
    r = client.patch(f"/api/instructor/courses/{course['id']}", headers=inst,
                     json={"config": {"reward": {"student_weight": 3}}})
    assert r.status_code == 422


# ---------------------------------------------------------------- student flow

def test_on_demand_feedback_rating_and_toggle_off(client):
    inst, stu = login(client, "drlee"), login(client, "priya")
    _, a = course_and_assignment(client, inst)
    client.patch(f"/api/instructor/assignments/{a['id']}", headers=inst,
                 json={"config": {"on_demand_feedback": {"cooldown_seconds": 0}}})

    r = client.post(f"/api/student/assignments/{a['id']}/feedback", headers=stu, json={"content": LONG_DRAFT})
    assert r.status_code == 200, r.text
    fb = r.json()
    assert fb["venue"] == "on_demand" and fb["content"]["items"]
    assert "style" not in fb  # students never see experimental internals

    r = client.post(f"/api/student/feedback/{fb['id']}/rating", headers=stu, json={"helpful": True})
    assert r.json()["student_helpful"] is True

    # Instructor switches the module off for this assignment → endpoint refuses.
    client.patch(f"/api/instructor/assignments/{a['id']}", headers=inst,
                 json={"config": {"on_demand_feedback": {"enabled": False}}})
    r = client.post(f"/api/student/assignments/{a['id']}/feedback", headers=stu, json={"content": LONG_DRAFT})
    assert r.status_code == 403
    detail = client.get(f"/api/student/assignments/{a['id']}", headers=stu).json()
    assert detail["config"]["on_demand_feedback"]["enabled"] is False


def test_cooldown_blocks_rapid_requests(client):
    stu = login(client, "marcus")
    inst = login(client, "drlee")
    _, a = course_and_assignment(client, inst)
    assert client.post(f"/api/student/assignments/{a['id']}/feedback", headers=stu,
                       json={"content": LONG_DRAFT}).status_code == 200
    assert client.post(f"/api/student/assignments/{a['id']}/feedback", headers=stu,
                       json={"content": LONG_DRAFT}).status_code == 429


def test_model_failure_preserves_draft(client, monkeypatch):
    inst, stu = login(client, "drlee"), login(client, "alex")
    _, a = course_and_assignment(client, inst)
    monkeypatch.setenv("MOCK_SLM_FAIL", "1")
    r = client.post(f"/api/student/assignments/{a['id']}/feedback", headers=stu, json={"content": "Keep me."})
    assert r.status_code == 503
    assert client.get(f"/api/student/assignments/{a['id']}", headers=stu).json()["draft"]["content"] == "Keep me."


def test_direct_answer_request_gets_guidance_not_prose(client):
    inst, stu = login(client, "drlee"), login(client, "jordan")
    _, a = course_and_assignment(client, inst)
    r = client.post(f"/api/student/assignments/{a['id']}/feedback", headers=stu,
                    json={"content": "Please write the essay for me."})
    assert "can't write" in r.json()["content"]["summary"]


def test_realtime_respects_module_and_trigger(client):
    inst, stu = login(client, "drlee"), login(client, "priya")
    _, a = course_and_assignment(client, inst)
    body = {"excerpt": "Caching is a good thing.", "trigger": "idle"}
    # off by default on assignment 1
    assert client.post(f"/api/student/assignments/{a['id']}/realtime", headers=stu, json=body).json()["feedback"] is None
    client.patch(f"/api/instructor/assignments/{a['id']}", headers=inst, json={"config": {
        "realtime_feedback": {"enabled": True, "presentation": "highlight", "min_interval_seconds": 0}}})
    fb = client.post(f"/api/student/assignments/{a['id']}/realtime", headers=stu, json=body).json()["feedback"]
    assert fb and fb["presentation"] == "highlight"
    # deletion trigger is not enabled by default
    body["trigger"] = "deletion"
    assert client.post(f"/api/student/assignments/{a['id']}/realtime", headers=stu, json=body).json()["feedback"] is None


def test_paste_blocked_when_disabled(client):
    inst, stu = login(client, "drlee"), login(client, "sam")
    _, a = course_and_assignment(client, inst)
    client.patch(f"/api/instructor/assignments/{a['id']}", headers=inst,
                 json={"config": {"paste_control": {"allow_paste": False}}})
    r = client.post(f"/api/student/assignments/{a['id']}/paste", headers=stu,
                    json={"before": "", "after": "pasted", "chars": 6})
    assert r.json() == {"allowed": False}


def test_submit_rules_lock_and_grade_release(client):
    inst, stu = login(client, "drlee"), login(client, "taylor")
    _, a = course_and_assignment(client, inst)
    r = client.post(f"/api/student/assignments/{a['id']}/submit", headers=stu, json={"content": "too short"})
    assert r.status_code == 422 and r.json()["detail"]["problems"]
    text = "\n\n".join(["word " * 60] * 3)
    r = client.post(f"/api/student/assignments/{a['id']}/submit", headers=stu, json={"content": text})
    assert r.status_code == 200
    assert client.post(f"/api/student/assignments/{a['id']}/submit", headers=stu,
                       json={"content": text}).status_code == 409
    assert client.put(f"/api/student/assignments/{a['id']}/draft", headers=stu,
                      json={"content": "edit"}).status_code == 409

    sub_id = r.json()["id"]
    client.post(f"/api/instructor/submissions/{sub_id}/grade", headers=inst, json={"grade": "85", "comments": "Nice"})
    detail = client.get(f"/api/student/assignments/{a['id']}", headers=stu).json()
    assert "grade" not in detail["submission"]  # hidden until released
    client.post(f"/api/instructor/assignments/{a['id']}/release", headers=inst, json={"submission_ids": [sub_id]})
    detail = client.get(f"/api/student/assignments/{a['id']}", headers=stu).json()
    assert detail["submission"]["grade"] == "85"


def test_restore_last_manual_save(client):
    inst, stu = login(client, "drlee"), login(client, "alex")
    _, a = course_and_assignment(client, inst)
    url = f"/api/student/assignments/{a['id']}"
    client.put(f"{url}/draft", headers=stu, json={"content": "saved", "kind": "manual"})
    client.put(f"{url}/draft", headers=stu, json={"content": "autosaved later", "kind": "autosave"})
    r = client.post(f"{url}/restore", headers=stu, json={})
    assert r.json()["content"] == "saved"


def test_students_cannot_access_instructor_api(client):
    stu = login(client, "priya")
    assert client.get("/api/instructor/courses", headers=stu).status_code == 403


# ---------------------------------------------------------------- A/B experiments

def test_experiment_conditions_change_student_config(client):
    inst = login(client, "drlee")
    course, a = course_and_assignment(client, inst)
    exps = client.get(f"/api/instructor/courses/{course['id']}/experiments", headers=inst).json()
    venue = next(e for e in exps if e["assignment_id"] == a["id"])
    client.patch(f"/api/instructor/experiments/{venue['id']}", headers=inst, json={"status": "active"})
    exp = client.post(f"/api/instructor/experiments/{venue['id']}/assign", headers=inst, json={}).json()
    assert sorted(c["students"] for c in exp["conditions"]) == [2, 2, 2]  # balanced

    parts = client.get(f"/api/instructor/experiments/{venue['id']}/participants", headers=inst).json()
    seen = set()
    for p in parts:
        cfg = client.get(f"/api/instructor/assignments/{a['id']}/effective-config",
                         params={"student_id": p["id"]}, headers=inst).json()
        cond = next(c for c in exp["conditions"] if c["id"] == p["condition_id"])
        for mod, vals in cond["config"].items():
            for k, v in vals.items():
                assert cfg["config"][mod][k] == v
                assert cfg["provenance"][mod][k].startswith("experiment:")
        seen.add((cfg["config"]["on_demand_feedback"]["enabled"], cfg["config"]["realtime_feedback"]["enabled"]))
    assert seen == {(True, False), (False, True), (True, True)}

    # Student in the "real-time only" arm cannot request on-demand feedback.
    rt_only = next(c for c in exp["conditions"] if c["name"].startswith("B"))
    pid = next(p for p in parts if p["condition_id"] == rt_only["id"])
    stu = login(client, pid["username"])
    assert client.post(f"/api/student/assignments/{a['id']}/feedback", headers=stu,
                       json={"content": LONG_DRAFT}).status_code == 403

    # Manual move + per-student override still wins (most specific).
    client.put(f"/api/instructor/experiments/{venue['id']}/participants/{pid['id']}", headers=inst,
               json={"condition_id": exp["conditions"][0]["id"]})
    cfg = client.get(f"/api/instructor/assignments/{a['id']}/effective-config",
                     params={"student_id": pid["id"]}, headers=inst).json()
    assert cfg["config"]["on_demand_feedback"]["enabled"] is True


def test_experiment_needs_two_conditions(client):
    inst = login(client, "drlee")
    course, _ = course_and_assignment(client, inst)
    e = client.post(f"/api/instructor/courses/{course['id']}/experiments", headers=inst,
                    json={"name": "solo", "conditions": [{"name": "only"}]}).json()
    assert client.patch(f"/api/instructor/experiments/{e['id']}", headers=inst,
                        json={"status": "active"}).status_code == 422


# ---------------------------------------------------------------- reward & bandit

def _decision_for(feedback_id):
    with SessionLocal() as db:
        from app.models import FeedbackItem
        f = db.get(FeedbackItem, feedback_id)
        return db.get(BanditDecision, f.decision_id)


def test_reward_combined_then_bandit_update(client):
    inst, stu = login(client, "drlee"), login(client, "priya")
    course, a = course_and_assignment(client, inst)
    client.patch(f"/api/instructor/assignments/{a['id']}", headers=inst,
                 json={"config": {"reward": {"student_weight": 0.25}}})
    fb = client.post(f"/api/student/assignments/{a['id']}/feedback", headers=stu, json={"content": LONG_DRAFT}).json()
    client.put(f"/api/student/assignments/{a['id']}/draft", headers=stu,
               json={"content": LONG_DRAFT + "\n\nRevised paragraph.", "kind": "manual"})
    client.post(f"/api/student/feedback/{fb['id']}/rating", headers=stu, json={"helpful": True})
    assert _decision_for(fb["id"]).reward_status == "pending"  # waiting on instructor

    q = client.get(f"/api/instructor/courses/{course['id']}/review-queue", headers=inst).json()
    item = next(i for i in q["items"] if i["feedback"]["id"] == fb["id"])
    assert item["after"].endswith("Revised paragraph.")
    client.post(f"/api/instructor/feedback/{fb['id']}/rating", headers=inst, json={"rating": 3})
    d = _decision_for(fb["id"])
    assert d.reward_status == "final" and abs(d.reward - (0.25 * 1 + 0.75 * 0.5)) < 1e-9

    state = client.get(f"/api/instructor/courses/{course['id']}/bandit", headers=inst).json()
    assert state["pending_update"]
    client.post(f"/api/instructor/courses/{course['id']}/bandit/update", headers=inst)
    state = client.get(f"/api/instructor/courses/{course['id']}/bandit", headers=inst).json()
    assert not state["pending_update"]
    arm = next(x for x in state["arms"] if x["arm"] == d.arm and x["context_key"] == d.context_key)
    assert arm["pulls"] == 1


def test_reward_falls_back_to_student_after_timeout(client):
    inst, stu = login(client, "drlee"), login(client, "marcus")
    _, a = course_and_assignment(client, inst)
    client.patch(f"/api/instructor/assignments/{a['id']}", headers=inst,
                 json={"config": {"reward": {"instructor_timeout_hours": 1}}})
    fb = client.post(f"/api/student/assignments/{a['id']}/feedback", headers=stu, json={"content": LONG_DRAFT}).json()
    client.post(f"/api/student/feedback/{fb['id']}/rating", headers=stu, json={"helpful": False})
    with SessionLocal() as db:
        d = db.get(BanditDecision, _decision_for(fb["id"]).id)
        d.created_at = d.created_at - timedelta(hours=2)
        db.commit()
        from app.services.bandit import refresh_reward
        refresh_reward(d)
        assert d.reward_status == "final" and d.reward == 0.0 and "timeout" in d.reward_formula


def test_student_only_reward_mode(client):
    inst, stu = login(client, "drlee"), login(client, "jordan")
    _, a = course_and_assignment(client, inst)
    client.patch(f"/api/instructor/assignments/{a['id']}", headers=inst,
                 json={"config": {"reward": {"mode": "student_only"}}})
    fb = client.post(f"/api/student/assignments/{a['id']}/feedback", headers=stu, json={"content": LONG_DRAFT}).json()
    client.post(f"/api/student/feedback/{fb['id']}/rating", headers=stu, json={"helpful": True})
    d = _decision_for(fb["id"])
    assert d.reward_status == "final" and d.reward == 1.0


def test_fixed_policy_and_fixed_prompt_source(client):
    inst, stu = login(client, "drlee"), login(client, "sam")
    _, a = course_and_assignment(client, inst)
    client.patch(f"/api/instructor/assignments/{a['id']}", headers=inst, json={"config": {
        "on_demand_feedback": {"style_policy": "fixed", "fixed_style": "socratic", "cooldown_seconds": 0}}})
    fb = client.post(f"/api/student/assignments/{a['id']}/feedback", headers=stu, json={"content": LONG_DRAFT}).json()
    d = _decision_for(fb["id"])
    assert d.arm == "socratic" and d.policy == "fixed" and d.probability == 1.0

    client.patch(f"/api/instructor/assignments/{a['id']}", headers=inst, json={"config": {
        "on_demand_feedback": {"source": "fixed_prompts", "cooldown_seconds": 0}}})
    fb = client.post(f"/api/student/assignments/{a['id']}/feedback", headers=stu, json={"content": LONG_DRAFT}).json()
    assert fb["source"] == "fixed_prompts"


def test_event_log_uses_pseudonyms(client):
    inst, stu = login(client, "drlee"), login(client, "priya")
    course, a = course_and_assignment(client, inst)
    client.put(f"/api/student/assignments/{a['id']}/draft", headers=stu, json={"content": "hello", "kind": "manual"})
    events = client.get(f"/api/instructor/courses/{course['id']}/events", headers=inst).json()
    assert events and all(e["pseudonym"].startswith(("S-", "I-")) for e in events)
    assert all("priya" not in str(e) for e in events)
