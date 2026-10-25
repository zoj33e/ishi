"""9x9 games against the HumanSL bot, with the fake KataGo (tests/fake_katago.py)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from ishi.engine.katago_process import KataGoProcess
from tests.conftest import FAKE_KATAGO


@pytest.fixture
def unlocked(monkeypatch: pytest.MonkeyPatch, api: TestClient) -> Iterator[TestClient]:
    from ishi.config import get_settings

    monkeypatch.setenv("ISHI_DEV_UNLOCK_ALL", "1")
    get_settings.cache_clear()
    yield api
    get_settings.cache_clear()


@pytest.fixture
def with_engine(unlocked: TestClient, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # These games end on a near-empty board, where the bot would otherwise fill dame (D-035).
    monkeypatch.setattr("ishi.play.full_game.dame_fill", lambda state, ownership: None)
    engine = KataGoProcess(FAKE_KATAGO)
    unlocked.portal.call(engine.start, 10)  # type: ignore[union-attr]
    unlocked.app.state.engine = engine  # type: ignore[attr-defined]
    yield unlocked
    unlocked.portal.call(engine.stop)  # type: ignore[union-attr]


def test_full_game_locked_before_yellow_belt(api: TestClient) -> None:
    r = api.post("/api/games", json={"mode": "full"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "MODE_LOCKED"
    assert api.get("/api/games/bot-ranks").json()["unlocked"] is False


def test_new_full_game_defaults_to_weakest_bot(unlocked: TestClient) -> None:
    ranks = unlocked.get("/api/games/bot-ranks").json()
    assert ranks["unlocked"] and ranks["ranks"][0] == 30
    g = unlocked.post("/api/games", json={"mode": "full"}).json()
    assert g["mode"] == "full" and g["board_size"] == 9 and g["komi"] == 7
    assert g["bot_label"] == "30k" and g["capture_target"] is None
    g2 = unlocked.post("/api/games", json={"mode": "full", "bot_rank": 0}).json()
    assert g2["bot_label"] == "1d"


def test_engine_offline_is_503(unlocked: TestClient) -> None:
    g = unlocked.post("/api/games", json={"mode": "full"}).json()
    r = unlocked.post(f"/api/games/{g['id']}/moves", json={"point": "E5"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "ENGINE_OFFLINE"
    assert unlocked.get(f"/api/games/{g['id']}").json()["move_number"] == 0  # nothing recorded


def test_bot_answers_and_two_passes_score_the_game(with_engine: TestClient) -> None:
    api = with_engine
    g = api.post("/api/games", json={"mode": "full", "bot_rank": 10}).json()
    r = api.post(f"/api/games/{g['id']}/moves", json={"point": "E5"}).json()
    assert r["bot_move"] not in (None, "pass", "E5") and r["state"]["move_number"] == 2
    # Learner passes; the (fake) engine then says pass is best, so the bot passes too.
    r = api.post(f"/api/games/{g['id']}/moves", json={"point": "pass"}).json()
    assert r["bot_move"] == "pass" and r["game_over"]
    s = r["state"]
    assert s["status"] == "finished" and s["result"] is not None
    assert (s["score"]["black_area"], s["score"]["white_area"]) == (1, 1)  # open board
    assert s["dead"] == []
    sgf = api.get(f"/api/games/{g['id']}/sgf").text
    assert "KM[7" in sgf and f"RE[{s['result']}]" in sgf


def test_learner_pass_after_bot_pass_ends_without_bot_turn(with_engine: TestClient) -> None:
    api = with_engine
    g = api.post("/api/games", json={"mode": "full"}).json()
    api.post(f"/api/games/{g['id']}/moves", json={"point": "pass"})  # bot answers pass
    state = api.get(f"/api/games/{g['id']}").json()
    assert state["status"] == "finished"  # pass + pass
