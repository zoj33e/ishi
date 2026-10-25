from fastapi.testclient import TestClient

from ishi.school.content import get_lesson
from tests.school.solutions import solve


def complete_lesson(api: TestClient, lesson_id: str) -> None:
    lesson = get_lesson(lesson_id)
    assert lesson is not None
    for task in lesson.tasks:
        for body in solve(lesson, task):
            r = api.post(f"/api/school/{lesson_id}/tasks/{task.id}/answer", json=body)
            assert r.status_code == 200, r.text
            assert r.json()["correct"], (lesson_id, task.id, body, r.json())


def test_school_list_unlocks_in_order(api: TestClient) -> None:
    body = api.get("/api/school").json()
    statuses = [lesson["status"] for lesson in body["lessons"]]
    assert statuses == ["available"] + ["locked"] * 9
    assert body["next_lesson"] == "R1"
    complete_lesson(api, "R1")
    body = api.get("/api/school").json()
    assert [lesson["status"] for lesson in body["lessons"]][:3] == ["done", "available", "locked"]


def test_lesson_detail_is_localized(api: TestClient) -> None:
    en = api.get("/api/school/R1?locale=en").json()
    th = api.get("/api/school/R1?locale=th").json()
    assert en["title"] != th["title"]
    assert en["tasks"][0]["position"]["board_size"] == en["board_size"]
    assert en["demo"], "demo frames"
    assert api.get("/api/school/R99").status_code == 404


def test_locked_lesson_rejects_answers(api: TestClient) -> None:
    r = api.post("/api/school/R2/tasks/t1/answer", json={"moves": ["C3"]})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "LESSON_LOCKED"


def test_wrong_answer_gives_feedback(api: TestClient) -> None:
    # R1 t2 asks for the center point (C3).
    r = api.post("/api/school/R1/tasks/t2/answer", json={"moves": ["A1"]}).json()
    assert r == {
        "correct": False,
        "feedback_key": "school.feedback.not_there",
        "marks": [],
        "done": False,
        "reply": None,
        "position": None,
        "lesson_done": False,
    }


def test_multi_step_play_returns_reply_and_position(api: TestClient) -> None:
    for lid in ["R1", "R2", "R3", "R4", "R5", "R6"]:
        complete_lesson(api, lid)
    lesson = get_lesson("R7")
    assert lesson is not None
    task = lesson.task("t2")
    assert task is not None
    first = solve(lesson, task)[0]
    r = api.post("/api/school/R7/tasks/t2/answer", json=first).json()
    assert r["correct"] and not r["done"]
    assert r["reply"] is not None
    assert r["position"]["last_move"] == r["reply"]


def test_all_ten_lessons_complete(api: TestClient) -> None:
    for i in range(1, 11):
        complete_lesson(api, f"R{i}")
    body = api.get("/api/school").json()
    assert all(lesson["status"] == "done" for lesson in body["lessons"])
    assert body["next_lesson"] is None
    assert api.get("/api/today").json()["school_next"] is None


def test_me_patch_locale(api: TestClient) -> None:
    me = api.get("/api/me").json()
    assert me["belt"] == "white"
    r = api.patch("/api/me", json={"locale": "en", "settings": {"sound": False}}).json()
    assert r["locale"] == "en" and r["settings"] == {"sound": False}
    assert api.get("/api/school").json()["lessons"][0]["title"] == "The board and taking turns"
