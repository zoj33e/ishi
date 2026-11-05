"""Progression (M8) through the API with the fake KataGo: rank updates after games, the adaptive
bot, belt exams (12 puzzles, then best of 3) and the progress screen."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from ishi.config import get_settings
from ishi.db.models import Exam, Game, Move, Puzzle, RankHistory, User, utcnow
from ishi.db.session import get_engine, get_or_create_user
from ishi.engine.katago_process import KataGoProcess
from ishi.gym import service as gym
from ishi.play import service
from ishi.play.review_service import AnalysisWorker
from ishi.rules.coords import Point, point_to_gtp
from tests.conftest import FAKE_KATAGO


def _db() -> Session:
    return Session(get_engine(get_settings().db_path))


def _set_user(**fields: object) -> None:
    with _db() as s:
        user = get_or_create_user(s)
        for k, v in fields.items():
            setattr(user, k, v)
        s.add(user)
        s.commit()


@pytest.fixture
def engine_api(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr("ishi.play.full_game.dame_fill", lambda state, ownership: None)
    engine = KataGoProcess(FAKE_KATAGO)
    api.portal.call(engine.start, 10)  # type: ignore[union-attr]
    api.app.state.engine = engine  # type: ignore[attr-defined]
    _set_user(belt="orange")
    yield api
    api.portal.call(engine.stop)  # type: ignore[union-attr]


def _finished_games(n: int, *, won: bool, bot_rank: float = 25.0, days_ago: int = 0) -> None:
    with _db() as s:
        user = get_or_create_user(s)
        for _ in range(n):
            s.add(
                Game(
                    user_id=user.id,
                    mode="full",
                    board_size=9,
                    bot_kind="humansl",
                    bot_rank=bot_rank,
                    status="finished",
                    result="B+R" if won else "W+R",
                    learner_won=won,
                    created_at=utcnow() - timedelta(days=days_ago),
                )
            )
        s.commit()


def test_rank_and_bot_follow_the_games(engine_api: TestClient) -> None:
    api = engine_api
    assert api.get("/api/today").json()["game"] == {
        "mode": "full",
        "board_size": 9,
        "bot_rank": 26.0,
    }
    assert api.get("/api/games/bot-ranks").json()["recommended"] == 26.0
    g = api.post("/api/games", json={"mode": "full"}).json()  # no rank: the adaptive one
    assert g["bot_label"] == "26k"
    for point in ("C3", "G7", "C7", "G3", "E3", "E7"):
        api.post(f"/api/games/{g['id']}/moves", json={"point": point})
    api.post(f"/api/games/{g['id']}/resign")
    engine = api.app.state.engine  # type: ignore[attr-defined]
    worker = AnalysisWorker(get_settings().db_path, lambda: engine)
    assert api.portal.call(worker.process, g["id"])  # type: ignore[union-attr]
    with _db() as s:
        game = s.get(Game, g["id"])
        assert game is not None and game.likelihood is not None
        assert set(game.likelihood) == {
            "moves",
            "rank_20k",
            "rank_15k",
            "rank_10k",
            "rank_5k",
            "rank_1d",
        }
        learner = s.exec(
            select(Move).where(Move.game_id == game.id, Move.by_learner, Move.number > 4)
        ).all()
        assert game.likelihood["moves"] == len(learner) > 0  # the opening skipped
        user = s.exec(select(User)).one()
        assert user.rank_estimate is not None and user.rank_estimate > 25.0  # a loss
        assert user.bot_rank == round(user.rank_estimate + 1)
        assert len(s.exec(select(RankHistory)).all()) == 1
    # a second pass over the same game changes nothing (likelihood stored)
    assert api.portal.call(worker.process, g["id"])  # type: ignore[union-attr]
    prog = api.get("/api/progress").json()
    assert prog["games_played"] == 1 and len(prog["rank_history"]) == 1
    assert [b["status"] for b in prog["belts"][:4]] == ["done", "done", "current", "next"]
    assert prog["exam"]["belt_target"] == "green" and prog["exam"]["rank_needed"] == 22.0
    assert prog["exam"]["available"] is False  # too weak yet, too few games


def _answer(api: TestClient, exam_id: str, pid: str, solve: bool) -> dict:
    with _db() as s:
        pz = s.get(Puzzle, pid)
        assert pz is not None
        state = gym.puzzle_state(pz)
    if not solve:
        wrong = next(
            point_to_gtp(p, pz.board_size)
            for p in (Point(x, y) for x in range(pz.board_size) for y in range(pz.board_size))
            if state.board[p] is None
            if not gym.grade(pz, [point_to_gtp(p, pz.board_size)])[0]
        )
        return api.post(
            f"/api/exams/{exam_id}/puzzles/{pid}/attempt", json={"moves": [wrong]}
        ).json()
    moves = [pz.correct_moves[0]]
    while True:
        r = api.post(f"/api/exams/{exam_id}/puzzles/{pid}/attempt", json={"moves": moves}).json()
        assert r["correct"]
        if r["done"]:
            return r
        moves.append(r["opponent_reply"])
        board = gym.replay(pz, moves).board
        group = board.group_at(gym._pt(pz.setup["target"], pz.board_size))
        assert group is not None
        libs = [point_to_gtp(p, pz.board_size) for p in group.liberties]
        moves.append(next(m for m in libs if gym.grade(pz, [*moves, m])[0]))


def _end_exam_game(game_id: str, *, won: bool) -> None:
    with _db() as s:
        game = s.get(Game, game_id)
        assert game is not None
        service.finish(
            s, game, service.load_state(s, game), "B+R" if won else "W+R", learner_won=won
        )
        s.commit()


def test_belt_exam_puzzles_then_best_of_three(engine_api: TestClient) -> None:
    api = engine_api
    assert api.post("/api/exams").status_code == 409  # not ready yet
    _set_user(rank_estimate=21.5)
    _finished_games(5, won=True)
    today = api.get("/api/today").json()
    assert today["exam_available"] and today["exam_belt"] == "green"
    exam = api.post("/api/exams").json()
    assert exam["phase"] == "puzzles" and len(exam["puzzles"]) == 12
    assert exam["bot_label"] == "20k" and exam["wins_needed"] == 2 and exam["puzzles_needed"] == 10
    concepts = {p["puzzle"]["concept_id"] for p in exam["puzzles"]}
    assert concepts == set(gym.open_concepts("orange"))  # every open concept, taken in turn
    assert api.post("/api/exams").json()["id"] == exam["id"]  # resumes
    r = api.post("/api/games", json={"mode": "full", "exam_id": exam["id"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "EXAM_NOT_READY"
    ids = [p["puzzle"]["id"] for p in exam["puzzles"]]
    for i, pid in enumerate(ids):
        out = _answer(api, exam["id"], pid, solve=i >= 2)
        assert out["done"] and out["solution_line"]
    again = api.post(f"/api/exams/{exam['id']}/puzzles/{ids[0]}/attempt", json={"moves": ["A1"]})
    assert again.status_code == 409
    exam = api.get(f"/api/exams/{exam['id']}").json()
    assert exam["phase"] == "games" and exam["puzzle_score"] == 10
    with _db() as s:  # exam answers never touch the Shape Gym schedule
        assert all(c.reps == 0 for c in s.exec(select(gym.SrsCard)).all())
    g1 = api.post("/api/games", json={"mode": "full", "exam_id": exam["id"]}).json()
    assert g1["exam_id"] == exam["id"] and g1["bot_label"] == "20k" and g1["nudges_left"] == 0
    assert api.get(f"/api/exams/{exam['id']}").json()["active_game"] == g1["id"]
    _end_exam_game(g1["id"], won=True)
    g2 = api.post("/api/games", json={"mode": "full", "exam_id": exam["id"]}).json()
    _end_exam_game(g2["id"], won=True)
    exam = api.get(f"/api/exams/{exam['id']}").json()
    assert exam["status"] == "passed" and exam["phase"] == "done"
    assert api.get("/api/me").json()["belt"] == "green"
    prog = api.get("/api/progress").json()
    assert prog["exam"]["belt_target"] == "blue" and prog["exam"]["games_since_belt"] == 0


def test_failed_puzzles_end_the_exam_and_retry_needs_three_games(engine_api: TestClient) -> None:
    api = engine_api
    _set_user(rank_estimate=21.0)
    _finished_games(5, won=False, days_ago=1)
    exam = api.post("/api/exams").json()
    ids = [p["puzzle"]["id"] for p in exam["puzzles"]]
    for pid in ids[:2]:
        _answer(api, exam["id"], pid, solve=False)
    assert api.get(f"/api/exams/{exam['id']}").json()["status"] == "in_progress"
    out = _answer(api, exam["id"], ids[2], solve=False)  # 10/12 out of reach
    assert out["exam"]["status"] == "failed" and out["exam"]["phase"] == "done"
    assert api.get("/api/me").json()["belt"] == "orange"
    assert not api.get("/api/today").json()["exam_available"]
    _finished_games(2, won=True)
    assert not api.get("/api/today").json()["exam_available"]
    _finished_games(1, won=True)
    assert api.get("/api/today").json()["exam_available"]
    with _db() as s:
        assert [e.status for e in s.exec(select(Exam)).all()] == ["failed"]
