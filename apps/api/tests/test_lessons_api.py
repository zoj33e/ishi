"""Post-game lessons through the API (M5), on games rebuilt from mined golden cases."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from ishi.config import get_settings
from ishi.db.models import Analysis, Game, Lesson, Move, NarrationCache, Puzzle, User, utcnow
from ishi.db.session import get_engine, get_or_create_user
from ishi.engine.models import AnalysisResponse
from ishi.play import lessons
from ishi.play.review_service import analysis_row, review_game
from ishi.rules.coords import point_to_gtp
from ishi.rules.sgf import parse_sgf
from tests.why.golden import GOLDEN

MISSED_CAPTURE = "missed_capture/mined_mine20_g01_m25"  # Black missed J5 capturing 4 stones


def seed_game(case_id: str, *, belt: str = "yellow", locale: str = "en") -> str:
    """A finished full game ending with the case's learner move, analyzed around that move,
    reviewed by the Why Engine (no lesson yet)."""
    path = GOLDEN / case_id
    sgf = parse_sgf((path / "position.sgf").read_text(encoding="utf-8"))
    with Session(get_engine(get_settings().db_path)) as s:
        user = get_or_create_user(s)
        user.belt, user.locale = belt, locale
        game = Game(
            user_id=user.id,
            mode="full",
            board_size=sgf.size,
            komi=sgf.komi,
            bot_kind="humansl",
            status="finished",
            result="W+R",
        )
        s.add_all([user, game])
        s.flush()
        n = len(sgf.moves)
        for i, (color, point) in enumerate(sgf.moves, start=1):
            s.add(
                Move(
                    user_id=user.id,
                    game_id=game.id,
                    number=i,
                    color=color.name.lower(),
                    point=point_to_gtp(point, sgf.size),
                    by_learner=color.name == "BLACK",
                )
            )
        for name, turn in (("analysis_before.json", n - 1), ("analysis_after.json", n)):
            resp = AnalysisResponse.model_validate_json((path / name).read_text("utf-8"))
            s.add(analysis_row(game, resp.model_copy(update={"turnNumber": turn}), "test"))
        s.commit()
        review_game(s, game, {})
        return game.id


@pytest.fixture
def game_id(api: TestClient) -> str:
    return seed_game(MISSED_CAPTURE)


def test_only_finished_full_games_have_lessons(api: TestClient) -> None:
    with Session(get_engine(get_settings().db_path)) as s:
        user = get_or_create_user(s)
        capture = Game(user_id=user.id, mode="capture", board_size=9, bot_kind="capture_bot")
        active = Game(user_id=user.id, mode="full", board_size=9, bot_kind="humansl")
        s.add_all([capture, active])
        s.commit()
        ids = capture.id, active.id
    assert api.get(f"/api/games/{ids[0]}/lesson").status_code == 404
    r = api.get(f"/api/games/{ids[1]}/lesson")
    assert r.status_code == 409 and r.json()["error"]["code"] == "GAME_NOT_FINISHED"
    assert api.get("/api/games/nope/lesson").status_code == 404


def test_unreviewed_game_without_engine_is_unavailable(api: TestClient) -> None:
    with Session(get_engine(get_settings().db_path)) as s:
        user = get_or_create_user(s)
        g = Game(user_id=user.id, mode="full", board_size=9, bot_kind="humansl", status="finished")
        s.add(g)
        s.commit()
        gid = g.id
    r = api.get(f"/api/games/{gid}/lesson")
    assert r.status_code == 202 and r.json() == {"status": "unavailable"}


def test_mistake_lesson_template_only(api: TestClient, game_id: str) -> None:
    r = api.get(f"/api/games/{game_id}/lesson")
    assert r.status_code == 200
    lesson = r.json()
    assert lesson["lesson_type"] == "mistake" and lesson["concept_id"] == "missed_capture"
    assert lesson["played_move"] == "F8" and lesson["move_number"] == 25
    assert lesson["can_retry"] and lesson["solution_line"] == [] and lesson["focus"] is None
    n = lesson["narration"]
    assert n["headline"] == "You could have captured 4 stones here."
    assert "J5" not in json.dumps(n)  # the answer stays hidden until the retry
    # the board is the position before the mistake: Black to play, F8 still empty
    pos = lesson["position"]
    assert pos["to_move"] == "black" and pos["move_number"] == 24
    assert "F8" not in pos["stones"]["black"]
    with Session(get_engine(get_settings().db_path)) as s:
        row = s.exec(select(Lesson)).one()
        assert row.narration_source == "template" and row.viewed_at is not None
    # same lesson again, now in Thai (template)
    th = api.get(f"/api/games/{game_id}/lesson", params={"locale": "th"}).json()
    assert th["lesson_id"] == lesson["lesson_id"]
    assert th["narration"]["headline"].startswith("ตานี้กินหมาก")


def test_retry_correct_first_time(api: TestClient, game_id: str) -> None:
    lesson = api.get(f"/api/games/{game_id}/lesson").json()
    r = api.post(f"/api/lessons/{lesson['lesson_id']}/retry", json={"point": "J5"}).json()
    assert r["correct"] and r["feedback_key"] == "lesson.retry.correct"
    after = r["lesson"]
    assert after["retry_result"] == "solved_first" and not after["can_retry"]
    assert after["solution_line"][0] == "B J5"
    frames = after["solution_frames"]
    assert len(frames) == len(after["solution_line"]) and frames[0]["last_move"] == "J5"
    assert "G5" not in frames[0]["stones"]["white"]  # J5 captured the four stones
    again = api.post(f"/api/lessons/{lesson['lesson_id']}/retry", json={"point": "J5"})
    assert again.status_code == 409


def test_retry_wrong_twice_shows_the_solution(api: TestClient, game_id: str) -> None:
    lid = api.get(f"/api/games/{game_id}/lesson").json()["lesson_id"]
    r = api.post(f"/api/lessons/{lid}/retry", json={"point": "A1"}).json()
    assert not r["correct"] and r["feedback_key"] == "lesson.retry.tryAgain"
    assert r["lesson"]["hint_level"] == 1 and r["lesson"]["solution_line"] == []
    r = api.post(f"/api/lessons/{lid}/retry", json={"point": "A2"}).json()
    assert r["feedback_key"] == "lesson.retry.solution"
    assert r["lesson"]["retry_result"] == "failed" and r["lesson"]["hint_level"] == 3
    assert r["lesson"]["solution_line"][0] == "B J5"


def test_illegal_retry_is_rejected(api: TestClient, game_id: str) -> None:
    lid = api.get(f"/api/games/{game_id}/lesson").json()["lesson_id"]
    r = api.post(f"/api/lessons/{lid}/retry", json={"point": "E5"})  # occupied
    assert r.status_code == 422 and r.json()["error"]["details"]["reason"] == "occupied"
    assert api.post(f"/api/lessons/{lid}/retry", json={"point": "Z9"}).status_code == 422


def test_hint_ladder(api: TestClient, game_id: str) -> None:
    lid = api.get(f"/api/games/{game_id}/lesson").json()["lesson_id"]
    h1 = api.post(f"/api/lessons/{lid}/hint").json()
    assert h1["hint_level"] == 1 and h1["focus"] is None
    h2 = api.post(f"/api/lessons/{lid}/hint").json()
    assert h2["hint_level"] == 2 and h2["focus"] == "J5" and h2["solution_line"] == []
    h3 = api.post(f"/api/lessons/{lid}/hint").json()
    assert h3["hint_level"] == 3 and h3["retry_result"] == "failed" and h3["solution_line"]
    assert api.post(f"/api/lessons/{lid}/hint").status_code == 409


def test_solved_after_hint(api: TestClient, game_id: str) -> None:
    lid = api.get(f"/api/games/{game_id}/lesson").json()["lesson_id"]
    api.post(f"/api/lessons/{lid}/hint")
    r = api.post(f"/api/lessons/{lid}/retry", json={"point": "J5"}).json()
    assert r["lesson"]["retry_result"] == "solved_hint"


def test_done_adds_a_puzzle_once(api: TestClient, game_id: str) -> None:
    lid = api.get(f"/api/games/{game_id}/lesson").json()["lesson_id"]
    assert api.post(f"/api/lessons/{lid}/done").json() == {"puzzle_added": True}
    assert api.post(f"/api/lessons/{lid}/done").json() == {"puzzle_added": True}
    with Session(get_engine(get_settings().db_path)) as s:
        [p] = s.exec(select(Puzzle)).all()
        assert p.source == "own_mistake" and p.concept_id == "missed_capture"
        assert p.correct_moves == ["J5"] and p.setup["to_move"] == "black"
        assert "F8" not in p.setup["black"] and p.solution_line[0] == "B J5"
        assert s.get(Lesson, lid).done_at is not None  # type: ignore[union-attr]
    assert api.get(f"/api/games/{game_id}/lesson").json()["done"]
    assert api.get("/api/today").json()["lesson_pending"] is None


def test_today_points_to_the_unfinished_lesson(api: TestClient, game_id: str) -> None:
    lesson = api.get(f"/api/games/{game_id}/lesson").json()
    assert lesson["severity"] == "medium"  # 3.7 points lost
    today = api.get("/api/today").json()
    assert today["lesson_pending"] == lesson["lesson_id"] and today["lesson_game"] == game_id


def test_locked_concept_gives_a_clean_lesson(api: TestClient) -> None:
    gid = seed_game(MISSED_CAPTURE, belt="white")  # missed_capture is taught from Yellow
    lesson = api.get(f"/api/games/{gid}/lesson").json()
    assert lesson["lesson_type"] == "clean" and not lesson["can_retry"]
    assert lesson["narration"]["marks"] == []
    assert api.post(f"/api/lessons/{lesson['lesson_id']}/done").json() == {"puzzle_added": False}


class FakeTeacher:
    def __init__(self, answer: str) -> None:
        self.answer, self.calls = answer, 0
        self.failing = False

    async def complete(self, user_message: str) -> str:
        self.calls += 1
        return self.answer

    async def close(self) -> None:
        pass


GOOD = {
    "headline": "Four stones were waiting to be captured.",
    "explanation": [
        "The opponent's 4 stones had only one liberty left.",
        "You played F8 instead, and they got a chance to live.",
    ],
    "question": "Where could you have captured them?",
    "hints": ["Count their liberties.", "Look inside the highlighted area."],
    "takeaway": "Check for stones in atari before every move.",
    "marks": [{"point": "F8", "kind": "cross", "label": None}],
}


def test_llm_narration_is_validated_and_cached(api: TestClient) -> None:
    teacher = FakeTeacher(json.dumps(GOOD))
    api.app.state.teacher = teacher  # type: ignore[attr-defined]
    g1 = seed_game(MISSED_CAPTURE)
    l1 = api.get(f"/api/games/{g1}/lesson").json()
    assert l1["narration"]["headline"] == GOOD["headline"] and teacher.calls == 1
    # The second game's facts differ only in concept_is_new (no longer new): one more call...
    api.get(f"/api/games/{seed_game(MISSED_CAPTURE)}/lesson")
    assert teacher.calls == 2
    # ...and a third game with the very same facts reuses the cached narration.
    l3 = api.get(f"/api/games/{seed_game(MISSED_CAPTURE)}/lesson").json()
    assert l3["narration"] == l1["narration"] and teacher.calls == 2
    with Session(get_engine(get_settings().db_path)) as s:
        assert len(s.exec(select(NarrationCache)).all()) == 2
        sources = {row.narration_source for row in s.exec(select(Lesson)).all()}
        assert sources == {"llm"}
    assert api.get("/api/health").json()["llm"] == "ok"


def test_bad_llm_narration_falls_back(api: TestClient) -> None:
    bad = GOOD | {"hints": ["Try J5.", "Look inside the highlighted area."]}  # gives it away
    api.app.state.teacher = FakeTeacher(json.dumps(bad))  # type: ignore[attr-defined]
    gid = seed_game(MISSED_CAPTURE)
    lesson = api.get(f"/api/games/{gid}/lesson").json()
    assert lesson["narration"]["headline"] == "You could have captured 4 stones here."
    with Session(get_engine(get_settings().db_path)) as s:
        row = s.exec(select(Lesson)).one()
        assert row.narration_source == "template" and row.llm_reject_reason == "reveals_answer"


def test_novelty_and_new_concept(api: TestClient) -> None:
    g1 = seed_game(MISSED_CAPTURE)
    first = api.get(f"/api/games/{g1}/lesson").json()
    g2 = seed_game(MISSED_CAPTURE)
    second = api.get(f"/api/games/{g2}/lesson").json()
    with Session(get_engine(get_settings().db_path)) as s:
        rows = {r.id: r for r in s.exec(select(Lesson)).all()}
        assert rows[first["lesson_id"]].fact_package["concept_is_new"] is True
        assert rows[second["lesson_id"]].fact_package["concept_is_new"] is False
        user = s.exec(select(User)).one()
        assert lessons.last_taught(s, user.id) == "missed_capture"


def test_worker_builds_the_lesson_after_review(api: TestClient, tmp_path: Path) -> None:
    """The review service's final step creates the lesson (no request needed)."""
    gid = seed_game(MISSED_CAPTURE)
    with Session(get_engine(get_settings().db_path)) as s:
        game = s.get(Game, gid)
        assert game is not None
        game.reviewed_at = utcnow()
        lesson = api.portal.call(lessons.build_lesson, s, game, None)  # type: ignore[union-attr]
        assert lesson.lesson_type == "mistake"
        assert s.exec(select(Analysis).where(Analysis.game_id == gid)).all()


class LateTeacher(FakeTeacher):
    async def complete(self, user_message: str) -> str:
        await asyncio.sleep(0.3)
        return await super().complete(user_message)


@pytest.mark.parametrize("viewed", [False, True])
async def test_late_narration_upgrades_an_unseen_lesson(api: TestClient, viewed: bool) -> None:
    gid = seed_game(MISSED_CAPTURE)
    teacher = LateTeacher(json.dumps(GOOD))
    with Session(get_engine(get_settings().db_path)) as s:
        game = s.get(Game, gid)
        assert game is not None
        build = lessons.build_lesson(s, game, teacher, "m", budget=0.05, keep_late=True)
        task = asyncio.ensure_future(build)
        await asyncio.sleep(0.15)  # the template lesson is saved: ready before Claude answers
        with Session(get_engine(get_settings().db_path)) as other:
            ready = other.exec(select(Lesson).where(Lesson.game_id == gid)).one()
            assert ready.narration_source == "template"
            if viewed:  # the learner opened it: the text must not change under them
                ready.viewed_at = utcnow()
                other.add(ready)
                other.commit()
        lesson = await task
        assert lesson.narration_source == ("template" if viewed else "llm")
        assert len(s.exec(select(NarrationCache)).all()) == 1  # cached either way
