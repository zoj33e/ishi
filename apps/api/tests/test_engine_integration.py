"""Real KataGo tests. Run on the PC only: `uv run pytest -m engine`."""

import time
from collections.abc import AsyncIterator

import pytest

from ishi.config import get_settings
from ishi.engine.katago_process import KataGoProcess
from ishi.engine.models import AnalysisQuery
from ishi.engine.queries import empty_board_query

pytestmark = pytest.mark.engine


@pytest.fixture
async def katago() -> AsyncIterator[KataGoProcess]:
    settings = get_settings()
    if not settings.katago_configured:
        pytest.skip("KataGo not configured; run scripts/setup_engine.ps1")
    engine = KataGoProcess(settings.katago_command(), auto_restart=False)
    await engine.start()
    yield engine
    await engine.stop()


async def test_empty_9x9_returns_move_infos_within_2s(katago: KataGoProcess) -> None:
    # Warm-up query so one-time costs (NN cache, lazy init) are not counted.
    await katago.analyze(empty_board_query("warmup", max_visits=10))
    t0 = time.perf_counter()
    [resp] = await katago.analyze(empty_board_query("m0-empty-9x9", max_visits=300), timeout=2)
    elapsed = time.perf_counter() - t0
    assert resp.moveInfos, "no moveInfos"
    assert resp.rootInfo.visits >= 1
    assert resp.ownership is not None and len(resp.ownership) == 81
    assert resp.policy is not None and len(resp.policy) == 82
    assert elapsed < 2.0, f"took {elapsed:.2f}s"


async def test_humansl_profile_returns_human_policy(katago: KataGoProcess) -> None:
    if get_settings().katago_human_model is None:
        pytest.skip("no HumanSL model configured")
    q = AnalysisQuery(
        id="m0-human",
        moves=[("B", "E5")],
        maxVisits=1,
        includePolicy=True,
        overrideSettings={"humanSLProfile": "rank_15k", "ignorePreRootHistory": False},
    )
    [resp] = await katago.analyze(q)
    assert resp.humanPolicy is not None and len(resp.humanPolicy) == 82
    assert resp.humanPolicy[4 * 9 + 4] == -1  # E5 is occupied -> illegal
