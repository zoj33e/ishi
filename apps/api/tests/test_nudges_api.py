"""Nudges (M7) through the API with the fake KataGo: gates, budget, hints and "play anyway".

The fake engine rates every move about the same, so the detector verdict is stubbed where a nudge
is needed; the real decision (`nudges.decide`) is tested on golden positions in
tests/play/test_nudges.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from ishi.config import get_settings
from ishi.db.models import Game, Move
from ishi.db.session import get_engine
from ishi.engine.katago_process import KataGoProcess
from ishi.play import nudges
from ishi.why.context import ConceptHit, MoveContext
from ishi.why.review import MoveReview
from tests.conftest import FAKE_KATAGO

HIT = ConceptHit("missed_capture", 6.0, {}, [frozenset()], {}, ["E5"])


@pytest.fixture
def full(monkeypatch: pytest.MonkeyPatch, api: TestClient) -> Iterator[TestClient]:
    monkeypatch.setenv("ISHI_DEV_UNLOCK_ALL", "1")
    get_settings.cache_clear()
    monkeypatch.setattr("ishi.play.full_game.dame_fill", lambda state, ownership: None)
    engine = KataGoProcess(FAKE_KATAGO)
    api.portal.call(engine.start, 10)  # type: ignore[union-attr]
    api.app.state.engine = engine  # type: ignore[attr-defined]
    yield api
    api.portal.call(engine.stop)  # type: ignore[union-attr]
    get_settings.cache_clear()


@pytest.fixture
def teachable(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every ghost move except E5 is a teachable missed capture; returns the moves judged."""
    judged: list[str] = []

    def decide(ctx: MoveContext, number: int, belt: str, limit: float, pf: float | None):
        judged.append(ctx.gtp(ctx.move))
        if ctx.gtp(ctx.move) == "E5":
            return None
        return MoveReview(number, ctx.gtp(ctx.move), 6.0, HIT, ctx), HIT

    monkeypatch.setattr(nudges, "decide", decide)
    monkeypatch.setattr(nudges, "FAST_SKIP", 0.0)  # the fake engine knows these moves
    return judged


def _new(api: TestClient) -> str:
    return api.post("/api/games", json={"mode": "full", "bot_rank": 20}).json()["id"]


def test_nudge_budget_hints_and_play_anyway(full: TestClient, teachable: list[str]) -> None:
    gid = _new(full)
    assert full.get(f"/api/games/{gid}").json()["nudges_left"] == 2
    assert full.post(f"/api/games/{gid}/preview", json={"point": "E5"}).json() == {
        "legal": True,
        "reason": None,
        "nudge": None,
    }
    r = full.post(f"/api/games/{gid}/preview", json={"point": "C3"}).json()
    n = r["nudge"]
    assert r["legal"] and n["concept_id"] == "missed_capture" and n["nudges_left"] == 1
    assert n["question"] and n["hint_level_available"] == 2
    assert "E5" not in " ".join([n["headline"], *n["explanation"], n["question"]])
    # the same ghost again: the same nudge, no budget used
    again = full.post(f"/api/games/{gid}/preview", json={"point": "C3"}).json()["nudge"]
    assert again["nudges_left"] == 1 and again["question"] == n["question"]
    # the screen is in the other language (the learner's is Thai): the same nudge, in English
    assert any("฀" <= c <= "๿" for c in n["question"])
    en = full.post(f"/api/games/{gid}/preview", json={"point": "C3", "locale": "en"}).json()
    assert en["nudge"]["nudges_left"] == 1 and en["nudge"]["question"] != n["question"]
    en1 = full.post(f"/api/games/{gid}/hint", json={"level": 1, "locale": "en"}).json()
    assert en1["text"].isascii()
    h1 = full.post(f"/api/games/{gid}/hint", json={"level": 1}).json()
    assert h1["text"] and h1["focus"] is None
    h2 = full.post(f"/api/games/{gid}/hint", json={"level": 2}).json()
    assert h2["focus"] and h2["focus"] != "E5"  # an area around the answer, not the answer
    assert full.post(f"/api/games/{gid}/hint", json={"level": 3}).status_code == 422
    # play anyway: the move counts, and is marked
    full.post(f"/api/games/{gid}/moves", json={"point": "C3"})
    with Session(get_engine(get_settings().db_path)) as s:
        m = s.exec(select(Move).where(Move.game_id == gid, Move.number == 1)).one()
        assert m.nudge_shown and m.played_anyway
        game = s.get(Game, gid)
        assert game is not None and "nudge" not in game.bot_params and game.nudges_used == 1
    r = full.post(f"/api/games/{gid}/hint", json={"level": 1})
    assert r.status_code == 409 and r.json()["error"]["code"] == "NO_NUDGE"
    # second nudge, then the budget is spent
    assert full.post(f"/api/games/{gid}/preview", json={"point": "G7"}).json()["nudge"]
    full.post(f"/api/games/{gid}/moves", json={"point": "E5"})  # rethought: not played anyway
    with Session(get_engine(get_settings().db_path)) as s:
        m = s.exec(select(Move).where(Move.game_id == gid, Move.number == 3)).one()
        assert m.nudge_shown and not m.played_anyway
    assert full.get(f"/api/games/{gid}").json()["nudges_left"] == 0
    assert full.post(f"/api/games/{gid}/preview", json={"point": "C7"}).json()["nudge"] is None


def test_no_nudges_in_exams_capture_games_or_when_switched_off(
    full: TestClient, teachable: list[str]
) -> None:
    capture = full.post("/api/games", json={"mode": "capture"}).json()
    r = full.post(f"/api/games/{capture['id']}/preview", json={"point": "C3"}).json()
    assert r == {"legal": True, "reason": None, "nudge": None} and capture["nudges_left"] == 0
    gid = _new(full)
    with Session(get_engine(get_settings().db_path)) as s:  # a belt-exam game (M8)
        game = s.get(Game, gid)
        assert game is not None
        game.mode = "exam"
        s.add(game)
        s.commit()
    assert full.post(f"/api/games/{gid}/preview", json={"point": "C3"}).json()["nudge"] is None
    off = _new(full)
    full.patch("/api/me", json={"settings": {"nudges": False}})
    assert full.post(f"/api/games/{off}/preview", json={"point": "C3"}).json()["nudge"] is None
    assert full.get(f"/api/games/{off}").json()["nudges_left"] == 0
    assert teachable == []  # never even analyzed


def test_preview_reports_illegal_moves(full: TestClient) -> None:
    gid = _new(full)
    full.post(f"/api/games/{gid}/moves", json={"point": "C3"})
    r = full.post(f"/api/games/{gid}/preview", json={"point": "C3"}).json()
    assert r == {"legal": False, "reason": "occupied", "nudge": None}
    r = full.post(f"/api/games/{gid}/preview", json={"point": "Z9"})
    assert r.status_code == 422


def test_no_nudge_without_engine(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ISHI_DEV_UNLOCK_ALL", "1")
    get_settings.cache_clear()
    gid = _new(api)
    r = api.post(f"/api/games/{gid}/preview", json={"point": "C3"}).json()
    assert r == {"legal": True, "reason": None, "nudge": None}
    get_settings.cache_clear()
