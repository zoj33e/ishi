"""Bot calibration (M3): adjacent-rank HumanSL bot matches on 9x9, appended to docs/calibration-log.md.

Usage (from apps/api):
    uv run python ../../scripts/calibrate_bots.py --games 50
    uv run python ../../scripts/calibrate_bots.py --pairs 30:28,28:26 --blunder 30=0.8,28=0.6

The stronger bot of each pair should win about 60% (04-katago-integration). Colors alternate,
komi 7, resignation on. Needs KataGo configured in .env.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from ishi.bots import humansl_bot
from ishi.bots.humansl_bot import profile_for, rank_label
from ishi.config import REPO_ROOT, get_settings
from ishi.engine.katago_process import KataGoProcess
from ishi.play.selfplay import SelfPlayResult, self_play
from ishi.rules.board import Color

DEFAULT_PAIRS = "30:28,28:26,26:24,24:22,22:20,20:15,15:10,10:5,5:0"
LOG = REPO_ROOT / "docs" / "calibration-log.md"
CONCURRENCY = 4  # = numAnalysisThreads


async def match(
    engine: KataGoProcess, weak: float, strong: float, games: int, seed: int
) -> tuple[int, int, list[SelfPlayResult]]:
    sem = asyncio.Semaphore(CONCURRENCY)
    pw, ps = profile_for(weak), profile_for(strong)

    async def one(i: int) -> tuple[bool, SelfPlayResult]:
        strong_black = i % 2 == 0
        async with sem:
            r = await self_play(
                engine,
                ps if strong_black else pw,
                pw if strong_black else ps,
                random.Random(seed * 1000 + i),
                gid=f"cal{rank_label(weak)}v{rank_label(strong)}g{i}",
            )
        strong_color = Color.BLACK if strong_black else Color.WHITE
        return r.winner is strong_color, r

    out = await asyncio.gather(*(one(i) for i in range(games)))
    strong_wins = sum(1 for won, r in out if won)
    draws = sum(1 for _, r in out if r.winner is None)
    return strong_wins, draws, [r for _, r in out]


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * q))]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=50)
    ap.add_argument("--pairs", default=DEFAULT_PAIRS)
    ap.add_argument("--blunder", default="", help="override weak blunder rates, e.g. 30=0.8,28=0.6")
    ap.add_argument("--temp", default="", help="override weak temperatures, e.g. 22=1.0")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-log", action="store_true")
    args = ap.parse_args()

    for item in filter(None, args.blunder.split(",")):
        rank, b = item.split("=")
        humansl_bot.WEAK_BLUNDER[int(rank)] = float(b)

    for item in filter(None, args.temp.split(",")):
        rank, t = item.split("=")
        humansl_bot.WEAK_TEMPERATURE[int(rank)] = float(t)

    pairs = [tuple(float(x) for x in p.split(":")) for p in args.pairs.split(",")]
    engine = KataGoProcess(get_settings().katago_command())
    await engine.start()
    rows, all_times = [], []
    t0 = time.time()
    try:
        for weak, strong in pairs:
            wins, draws, results = await match(engine, weak, strong, args.games, args.seed)
            times = [t for r in results for t in r.move_seconds]
            all_times += times
            resigned = sum(1 for r in results if r.result.endswith("+R"))
            length = statistics.mean(r.moves for r in results)
            row = (
                f"| {rank_label(weak)} vs {rank_label(strong)} | {profile_for(weak).blunder:.2f} "
                f"| {wins}/{args.games} ({100 * wins / args.games:.0f}%) | {draws} | {resigned} "
                f"| {length:.0f} | {pct(times, 0.95) * 1000:.0f} |"
            )
            rows.append(row)
            print(row, flush=True)
    finally:
        await engine.stop()

    elapsed = time.time() - t0
    summary = (
        f"\n## {datetime.now(UTC):%Y-%m-%d %H:%M} UTC — {args.games} games per pair, seed {args.seed}\n\n"
        f"Weak blunder rates: {dict(sorted(humansl_bot.WEAK_BLUNDER.items()))}, "
        f"temperatures: {dict(sorted(humansl_bot.WEAK_TEMPERATURE.items()))}. "
        f"Bot visits {humansl_bot.BOT_VISITS}. All bot moves: p50 {pct(all_times, 0.5) * 1000:.0f} ms, "
        f"p95 {pct(all_times, 0.95) * 1000:.0f} ms. Run time {elapsed / 60:.1f} min.\n\n"
        "| Match (weak vs strong) | weak blunder | strong wins | draws | resigned | avg moves | p95 ms |\n"
        "|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n"
    )
    print(summary)
    if not args.no_log:
        if not LOG.exists():
            LOG.write_text(
                "# Bot calibration log\n\nAppended by `scripts/calibrate_bots.py`. Target: the "
                "stronger bot of each adjacent pair wins about 60%.\n",
                encoding="utf-8",
            )
        with LOG.open("a", encoding="utf-8") as f:
            f.write(summary)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
