"""Shape Gym through the API (M6) with a frozen clock: the due queue across simulated days,
answers in the best set, hints and the FSRS rating rule."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from ishi.api.routes_gym import get_now
from ishi.config import get_settings
from ishi.db.models import Puzzle, PuzzleAttempt, SrsCard
from ishi.db.session import get_engine, get_or_create_user
from ishi.gym import fsrs_service
from ishi.gym import service as gym
from ishi.gym.puzzles import Outcome, load_seed, rating

BKK = timezone(timedelta(hours=7))
DAY0 = datetime(2026, 11, 2, 19, 30, tzinfo=BKK)  # an evening session


class Clock:
    def __init__(self) -> None:
        self.now = DAY0

    def day(self, n: int, hour: int = 8) -> None:
        self.now = (DAY0 + timedelta(days=n)).replace(hour=hour, minute=0)


@pytest.fixture
def clock(api: TestClient) -> Iterator[Clock]:
    c = Clock()
    api.app.dependency_overrides[get_now] = lambda: c.now  # type: ignore[attr-defined]
    yield c
    api.app.dependency_overrides.clear()  # type: ignore[attr-defined]


def _db() -> Session:
    return Session(get_engine(get_settings().db_path))


def _solve(api: TestClient, pid: str, **extra: object) -> dict:
    with _db() as s:
        p = s.get(Puzzle, pid)
        assert p is not None
        answer, line = p.correct_moves[0], p.solution_line
    moves = [answer]
    while True:
        r = api.post(f"/api/gym/puzzles/{pid}/attempt", json={"moves": moves, **extra}).json()
        assert r["correct"], r
        if r["done"]:
            return r
        reply = r["opponent_reply"]
        # the next learner move: the solution line's, or any atari that keeps the chase going
        nxt = line[len(moves) + 1].split()[-1] if len(line) > len(moves) + 1 else None
        moves += [reply, nxt]


def _wrong(pid: str) -> str:
    with _db() as s:
        p = s.get(Puzzle, pid)
        assert p is not None
        stones = set(p.setup["black"]) | set(p.setup["white"])
        return next(m for m in p.setup["region"] if m not in p.correct_moves and m not in stones)


def test_rating_rule() -> None:
    assert rating(Outcome(True, time_ms=3000)) == "easy"
    assert rating(Outcome(True, time_ms=9000)) == "good"
    assert rating(Outcome(True, hints_used=1, time_ms=3000)) == "hard"
    assert rating(Outcome(True, wrong_tries=1)) == "hard"
    assert rating(Outcome(False)) == "again"


def test_fsrs_is_day_based_and_deterministic() -> None:
    card = fsrs_service.new_card("u", "p", DAY0)
    fsrs_service.review(card, "again", DAY0)
    assert card.due_at - DAY0 == timedelta(days=1)  # tomorrow, not in 10 minutes
    assert card.lapses == 0 and card.reps == 1
    fsrs_service.review(card, "good", card.due_at)
    first = card.due_at
    fsrs_service.review(card, "again", first)
    assert card.lapses == 1  # a learned card forgotten
    again = fsrs_service.new_card("u", "p", DAY0)
    fsrs_service.review(again, "again", DAY0)
    fsrs_service.review(again, "good", again.due_at)
    assert again.due_at == first  # no fuzzing


def test_warmup_tops_up_with_seed_puzzles(api: TestClient, clock: Clock) -> None:
    assert api.get("/api/today").json()["warmup_due"] == 0
    r = api.get("/api/gym/due", params={"context": "warmup"}).json()
    assert r["due_today"] == 0 and len(r["puzzles"]) == 3
    # a new learner (White belt) practises the Yellow concepts, weakest (here: first) first
    assert {p["concept_id"] for p in r["puzzles"]} == {"missed_capture"}
    first = r["puzzles"][0]
    assert first["source"] == "seed" and first["position"]["stones"]["black"]
    assert first["to_move"] == first["position"]["to_move"]
    # served cards stay due until answered; asking again gives the same puzzles
    again = api.get("/api/gym/due", params={"context": "warmup"}).json()
    assert [p["id"] for p in again["puzzles"]] == [p["id"] for p in r["puzzles"]]
    assert api.get("/api/today").json()["warmup_due"] == 3


def test_due_queue_across_simulated_days(api: TestClient, clock: Clock) -> None:
    ids = [p["id"] for p in api.get("/api/gym/due", params={"context": "warmup"}).json()["puzzles"]]
    easy, good, failed = ids
    assert _solve(api, easy, time_ms=2000)["rating"] == "easy"
    assert _solve(api, good, time_ms=9000)["rating"] == "good"
    w = _wrong(failed)
    with _db() as db:
        setup = db.get(Puzzle, failed).setup  # type: ignore[union-attr]
        first_board = {"black": setup["black"], "white": setup["white"]}
    assert api.post(f"/api/gym/puzzles/{failed}/attempt", json={"moves": [w]}).json() == {
        "correct": False,
        "done": False,
        "solved": False,
        "opponent_reply": None,
        "solution_line": None,
        "solution_frames": None,
        "rating": None,
        "next_due_at": None,
        "board": {"stones": first_board, "last_move": None},  # unchanged after a wrong move
    }
    r = api.post(f"/api/gym/puzzles/{failed}/attempt", json={"moves": [w], "wrong_tries": 1}).json()
    assert r["done"] and not r["solved"] and r["rating"] == "again" and r["solution_line"]
    assert api.get("/api/today").json()["warmup_due"] == 0  # all answered today

    def due_ids() -> list[str]:
        """Today's due cards (without serving new seed puzzles)."""
        with _db() as s:
            user = get_or_create_user(s)
            due = [p.id for p in gym._due(s, user.id, clock.now, 8)]
        assert api.get("/api/today").json()["warmup_due"] == len(due)
        return due

    clock.day(1)
    assert due_ids() == [failed]  # Again: tomorrow
    clock.day(1, hour=23)
    assert due_ids() == [failed]  # due all day
    clock.day(2)
    assert set(due_ids()) == {failed, good}  # not reviewed yesterday; Good: in 2 days
    _solve(api, failed, time_ms=9000)
    _solve(api, good, time_ms=9000)
    clock.day(3)
    assert due_ids() == []
    with _db() as s:
        cards = {c.puzzle_id: c for c in s.exec(select(SrsCard)).all()}
    easy_day = (cards[easy].due_at.astimezone(BKK).date() - DAY0.date()).days
    assert easy_day == 8  # Easy: a week later
    clock.day(easy_day)
    assert easy in due_ids()
    with _db() as s:
        results = [a.result for a in s.exec(select(PuzzleAttempt)).all()]
    assert sorted(results) == ["again", "easy", "good", "good", "good"]


def test_any_move_in_the_best_set_is_accepted(api: TestClient, clock: Clock) -> None:
    item = next(i for i in load_seed() if len(i["correct_moves"]) > 1 and i["learner_moves"] == 1)
    with _db() as s:
        user = get_or_create_user(s)
        user.belt = "black"  # every concept open
        s.add(user)
        s.commit()
        p = next(p for p in gym.serve_seeds(s, user, clock.now, 103) if p.seed_id == item["id"])
        s.commit()
        pid = p.id
    for move in item["correct_moves"]:
        r = api.post(f"/api/gym/puzzles/{pid}/attempt", json={"moves": [move]}).json()
        assert r["correct"] and r["solved"], move


def test_hints(api: TestClient, clock: Clock) -> None:
    pid = api.get("/api/gym/due", params={"context": "warmup"}).json()["puzzles"][0]["id"]
    h1 = api.post(f"/api/gym/puzzles/{pid}/hint", json={"level": 1}).json()
    assert h1["concept_id"] == "missed_capture" and h1["marks"] and h1["focus"] is None
    h2 = api.post(f"/api/gym/puzzles/{pid}/hint", json={"level": 2}).json()
    with _db() as s:
        p = s.get(Puzzle, pid)
        assert p is not None and h2["focus"] == p.correct_moves[0]
        assert h2["solution_line"] is None
    assert _solve(api, pid, hints_used=2, time_ms=2000)["rating"] == "hard"
    pid2 = api.get("/api/gym/due", params={"context": "gym"}).json()["puzzles"][0]["id"]
    h3 = api.post(f"/api/gym/puzzles/{pid2}/hint", json={"level": 3}).json()
    assert h3["rating"] == "again" and h3["solution_line"] and h3["solution_frames"]


def test_bad_sequences_and_unknown_puzzles(api: TestClient, clock: Clock) -> None:
    pid = api.get("/api/gym/due").json()["puzzles"][0]["id"]
    r = api.post(f"/api/gym/puzzles/{pid}/attempt", json={"moves": ["A1", "A2"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "BAD_MOVES"
    r = api.post("/api/gym/puzzles/nope/attempt", json={"moves": ["A1"]})
    assert r.status_code == 404 and r.json()["error"]["code"] == "PUZZLE_NOT_FOUND"
