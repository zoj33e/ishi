import random

from fastapi.testclient import TestClient
from sqlmodel import Session

from ishi.config import get_settings
from ishi.db.models import Exam, Game
from ishi.db.session import get_engine, get_or_create_user
from ishi.play import service
from ishi.play.progression import (
    STAGES,
    ExamRecord,
    PlayedGame,
    current_stage,
    exam_available,
    exam_outcome,
)
from tests.test_school_api import complete_lesson


def _session() -> Session:
    return Session(get_engine(get_settings().db_path))


def _add_finished(n: int, *, won: bool, stage: int = 1, exam_id: str | None = None) -> None:
    with _session() as s:
        user = get_or_create_user(s)
        st = STAGES[stage - 1]
        for _ in range(n):
            s.add(
                Game(
                    user_id=user.id,
                    mode="capture",
                    board_size=st.board_size,
                    komi=0,
                    bot_kind="capture_bot",
                    bot_params={"level": st.level, "target": st.target, "stage": stage},
                    status="finished",
                    result="B+C" if won else "W+C",
                    learner_won=won,
                    exam_id=exam_id,
                )
            )
        s.commit()


def _play_out(api: TestClient, game_id: str, size: int, seed: int = 0) -> dict:
    rng = random.Random(seed)
    cols = "ABCDEFGHJ"[:size]
    points = [f"{c}{r}" for c in cols for r in range(1, size + 1)]
    for _ in range(500):
        rng.shuffle(points)
        for p in [*points, "pass"]:
            r = api.post(f"/api/games/{game_id}/moves", json={"point": p})
            if r.status_code == 200:
                break
            assert r.json()["error"]["code"] == "ILLEGAL_MOVE"
        body = r.json()
        if body["game_over"]:
            return body
    raise AssertionError("game did not finish")


def test_capture_game_starts_at_stage_one(api: TestClient) -> None:
    g = api.post("/api/games", json={"mode": "capture"}).json()
    assert g["board_size"] == 7 and g["capture_target"] == 1 and g["bot_level"] == 1
    assert g["learner_color"] == "black" and g["to_move"] == "black"
    assert api.get(f"/api/games/{g['id']}").json()["id"] == g["id"]


def test_move_gets_bot_reply_and_game_ends(api: TestClient) -> None:
    g = api.post("/api/games", json={}).json()
    r = api.post(f"/api/games/{g['id']}/moves", json={"point": "D4"}).json()
    assert r["bot_move"] is not None and r["state"]["move_number"] == 2
    final = _play_out(api, g["id"], 7)
    assert final["state"]["status"] == "finished"
    assert final["state"]["result"] in ("B+C", "W+C", "Draw")
    after = api.post(f"/api/games/{g['id']}/moves", json={"point": "A1"})
    assert after.status_code == 422
    assert after.json()["error"]["details"]["reason"] == "game_over"
    sgf = api.get(f"/api/games/{g['id']}/sgf").text
    assert sgf.startswith("(;GM[1]") and "RE[" in sgf


def test_illegal_and_bad_moves(api: TestClient) -> None:
    g = api.post("/api/games", json={}).json()
    api.post(f"/api/games/{g['id']}/moves", json={"point": "D4"})
    r = api.post(f"/api/games/{g['id']}/moves", json={"point": "D4"})
    assert r.status_code == 422 and r.json()["error"]["details"]["reason"] == "occupied"
    r = api.post(f"/api/games/{g['id']}/moves", json={"point": "Z9"})
    assert r.json()["error"]["code"] == "BAD_COORDINATE"
    assert api.get("/api/games/nope").status_code == 404


def test_resign_counts_as_loss(api: TestClient) -> None:
    g = api.post("/api/games", json={}).json()
    r = api.post(f"/api/games/{g['id']}/resign").json()
    assert r["status"] == "finished" and r["result"] == "W+R"


def test_three_wins_in_a_row_move_up_a_stage(api: TestClient) -> None:
    _add_finished(2, won=True)
    assert api.get("/api/today").json()["capture"]["stage"] == 1
    _add_finished(1, won=True)
    today = api.get("/api/today").json()
    assert today["capture"]["stage"] == 2 and today["capture"]["streak"] == 0
    g = api.post("/api/games", json={}).json()
    assert g["board_size"] == 9 and g["capture_target"] == 1


def test_stage_rules() -> None:
    w, lose = PlayedGame(1, True), PlayedGame(1, False)
    assert current_stage([w, w, lose, w, w]).stage.number == 1
    assert current_stage([w, w, w]).stage.number == 2
    top = [PlayedGame(s.number, True) for s in STAGES for _ in range(3)]
    assert current_stage(top * 2).stage.number == 5  # stays at the last stage


def test_exam_rules() -> None:
    assert not exam_available("white", True, 4, [])
    assert not exam_available("white", False, 9, [])
    assert exam_available("white", True, 5, [])
    assert not exam_available("yellow", True, 9, [])
    assert not exam_available("white", True, 9, [ExamRecord("failed", 2)])
    assert exam_available("white", True, 9, [ExamRecord("failed", 3)])
    assert not exam_available("white", True, 9, [ExamRecord("in_progress", 0)])
    assert exam_outcome(3, 2) == "passed"
    assert exam_outcome(2, 3) == "failed"
    assert exam_outcome(2, 2) == "in_progress"


def test_yellow_exam_flow(api: TestClient) -> None:
    assert api.get("/api/today").json()["exam_available"] is False
    assert api.post("/api/exams").status_code == 409
    for i in range(1, 11):
        complete_lesson(api, f"R{i}")
    _add_finished(5, won=False)
    assert api.get("/api/today").json()["exam_available"] is True

    exam = api.post("/api/exams").json()
    assert exam["status"] == "in_progress" and exam["wins_needed"] == 3
    g = api.post("/api/games", json={"exam_id": exam["id"]}).json()
    assert g["exam_id"] == exam["id"] and g["board_size"] == 9
    assert g["capture_target"] == 3 and g["bot_level"] == 2
    assert api.get(f"/api/exams/{exam['id']}").json()["active_game"] == g["id"]

    # Win three exam games (finished through the service, as the bot is too strong for a script).
    with _session() as s:
        user = get_or_create_user(s)
        for _ in range(3):
            game = service.start_game(s, user, s.get(Exam, exam["id"]))
            service.finish(s, game, service.load_state(s, game), "B+C", learner_won=True)
            s.commit()
    done = api.get(f"/api/exams/{exam['id']}").json()
    assert done["status"] == "passed" and done["games_won"] == 3
    assert api.get("/api/me").json()["belt"] == "yellow"
    assert api.get("/api/today").json()["exam_available"] is False
