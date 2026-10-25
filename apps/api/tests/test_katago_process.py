import asyncio

import pytest

from ishi.engine.katago_process import (
    EngineRestartedError,
    EngineUnavailableError,
    KataGoProcess,
    KataGoQueryError,
)
from ishi.engine.models import AnalysisQuery
from ishi.engine.queries import empty_board_query

from .conftest import FAKE_KATAGO


async def test_start_reads_version(fake_engine: KataGoProcess) -> None:
    assert fake_engine.ready
    assert fake_engine.version == "fake-1.0"
    assert await fake_engine.ping()


async def test_empty_board_query_parses(fake_engine: KataGoProcess) -> None:
    [resp] = await fake_engine.analyze(empty_board_query("t-empty"))
    assert resp.id == "t-empty"
    assert resp.moveInfos[0].move == "E5"
    assert resp.rootInfo.currentPlayer == "B"
    assert resp.ownership is not None and len(resp.ownership) == 81


async def test_multi_turn_out_of_order_sorted(fake_engine: KataGoProcess) -> None:
    q = AnalysisQuery(id="t-multi", moves=[("B", "E5"), ("W", "D4")], analyzeTurns=[0, 1, 2])
    resps = await fake_engine.analyze(q)
    assert [r.turnNumber for r in resps] == [0, 1, 2]


async def test_concurrent_queries_dispatch_by_id(fake_engine: KataGoProcess) -> None:
    results = await asyncio.gather(
        *(fake_engine.analyze(empty_board_query(f"t-c{i}")) for i in range(20))
    )
    assert [r[0].id for r in results] == [f"t-c{i}" for i in range(20)]


async def test_query_error_raises(fake_engine: KataGoProcess) -> None:
    with pytest.raises(KataGoQueryError, match="bad field"):
        await fake_engine.analyze(empty_board_query("bad-1"))


async def test_timeout(fake_engine: KataGoProcess) -> None:
    with pytest.raises(TimeoutError):
        await fake_engine.analyze(empty_board_query("hang-1"), timeout=0.3)
    assert await fake_engine.ping()


async def test_crash_fails_inflight_and_restarts(fake_engine: KataGoProcess) -> None:
    with pytest.raises(EngineRestartedError):
        await fake_engine.analyze(empty_board_query("crash-1"))
    assert not fake_engine.ready
    for _ in range(100):
        if fake_engine.ready:
            break
        await asyncio.sleep(0.05)
    assert fake_engine.ready
    [resp] = await fake_engine.analyze(empty_board_query("after-restart"))
    assert resp.id == "after-restart"


async def test_not_started_raises() -> None:
    engine = KataGoProcess(FAKE_KATAGO)
    with pytest.raises(EngineUnavailableError):
        await engine.analyze(empty_board_query("x"))
    assert not await engine.ping()


async def test_stop_then_query_raises(fake_engine: KataGoProcess) -> None:
    await fake_engine.stop()
    with pytest.raises(EngineUnavailableError):
        await fake_engine.analyze(empty_board_query("x"))


def test_query_serializes_rules_object() -> None:
    payload = empty_board_query("x").model_dump(exclude_none=True)
    assert payload["rules"] == {
        "ko": "SIMPLE",
        "scoring": "AREA",
        "tax": "NONE",
        "suicide": False,
        "hasButton": False,
        "whiteHandicapBonus": "0",
        "friendlyPassOk": True,
    }
    assert payload["komi"] == 7
    assert "overrideSettings" not in payload
