"""M3 acceptance with the real KataGo (`uv run pytest -m engine`): bot latency and scoring."""

import asyncio
import random
import time
from collections.abc import AsyncIterator

import pytest

from ishi.bots.humansl_bot import profile_for
from ishi.config import get_settings
from ishi.engine.katago_process import KataGoProcess
from ishi.play.full_game import bot_turn
from ishi.play.selfplay import SelfPlayResult, self_play
from ishi.rules.game import new_game, play

pytestmark = pytest.mark.engine

CLOSE_GAME = 20.0  # points


@pytest.fixture
async def katago() -> AsyncIterator[KataGoProcess]:
    settings = get_settings()
    if not settings.katago_configured:
        pytest.skip("KataGo not configured; run scripts/setup_engine.ps1")
    engine = KataGoProcess(settings.katago_command(), auto_restart=False)
    await engine.start()
    yield engine
    await engine.stop()


async def test_bot_move_p95_under_500ms(katago: KataGoProcess) -> None:
    """One game's worth of sequential bot moves, as the learner would see them."""
    rng = random.Random(7)
    state = new_game(9, 7)
    times = []
    for i in range(60):
        if state.is_over:
            break
        t0 = time.perf_counter()
        turn = await bot_turn(
            katago, state, profile_for(10), rng, resign_streak=0, qid=f"lat{i}", allow_resign=False
        )
        times.append(time.perf_counter() - t0)
        state = play(state, turn.point)
    times.sort()
    p95 = times[int(len(times) * 0.95)]
    print(f"bot move p50 {times[len(times) // 2] * 1000:.0f} ms, p95 {p95 * 1000:.0f} ms")
    assert p95 < 0.5


async def test_final_score_matches_katago_on_10_games(katago: KataGoProcess) -> None:
    """Games played to two passes (no resigning). Our area score after removing ownership-dead
    stones must be within 1 point of KataGo's final count (its ownership, point by point), and of
    its scoreLead when the game is close (D-036: scoreLead drifts by points in blowouts)."""
    sem = asyncio.Semaphore(4)

    async def one(i: int) -> SelfPlayResult:
        async with sem:
            return await self_play(
                katago,
                profile_for(12),
                profile_for(12),
                random.Random(100 + i),
                gid=f"score{i}",
                allow_resign=False,
            )

    results = await asyncio.gather(*(one(i) for i in range(10)))
    for i, r in enumerate(results):
        assert r.our_margin is not None and r.katago_lead is not None
        assert r.katago_count is not None
        print(
            f"game {i}: {r.moves} moves, ours {r.our_margin:+.1f}, "
            f"katago count {r.katago_count:+.1f}, lead {r.katago_lead:+.2f}"
        )
    count_diffs = [abs(r.our_margin - r.katago_count) for r in results]  # type: ignore[operator]
    assert max(count_diffs) <= 1.0, count_diffs
    close = [r for r in results if abs(r.katago_lead) < CLOSE_GAME]  # type: ignore[arg-type]
    lead_diffs = [abs(r.our_margin - r.katago_lead) for r in close]  # type: ignore[operator]
    assert not lead_diffs or max(lead_diffs) <= 1.0, lead_diffs
