"""Record KataGo analysis fixtures for Why Engine golden tests (11-testing).

Usage (from apps/api):
    uv run python ../../scripts/record_fixture.py tests/golden/missed_capture/atari_center [...]
    uv run python ../../scripts/record_fixture.py --all

Each case directory holds `position.sgf` (setup stones + moves; the last move is the learner's).
Writes `analysis_before.json` (the position the learner moved in) and `analysis_after.json` (right
after the move), at the post-game visit budget. Tests then run without the engine.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from ishi.config import get_settings
from ishi.engine.katago_process import KataGoProcess
from ishi.engine.queries import game_analysis_query
from ishi.rules.sgf import parse_sgf

GOLDEN = Path(__file__).resolve().parents[1] / "apps" / "api" / "tests" / "golden"


async def record(engine: KataGoProcess, case: Path) -> None:
    state = parse_sgf((case / "position.sgf").read_text(encoding="utf-8")).to_state()
    n = state.move_number
    if n < 1:
        raise ValueError(f"{case}: position.sgf needs the learner's move")
    query = game_analysis_query(f"golden-{case.parent.name}-{case.name}", state, [n - 1, n])
    responses = sorted(await engine.analyze(query), key=lambda r: r.turnNumber)
    for name, resp in zip(("analysis_before.json", "analysis_after.json"), responses, strict=True):
        data = resp.model_dump(exclude_none=True)
        (case / name).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"recorded {case.parent.name}/{case.name}", flush=True)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*", type=Path)
    ap.add_argument("--all", action="store_true", help="every case under tests/golden")
    ap.add_argument("--missing", action="store_true", help="only cases without fixtures")
    args = ap.parse_args()
    cases = sorted(p.parent for p in GOLDEN.glob("*/*/position.sgf")) if args.all else args.cases
    if args.missing:
        cases = [c for c in cases if not (c / "analysis_after.json").exists()]
    engine = KataGoProcess(get_settings().katago_command())
    await engine.start()
    sem = asyncio.Semaphore(4)  # = numAnalysisThreads; more would queue past the query timeout

    async def one(case: Path) -> None:
        async with sem:
            await record(engine, case)

    try:
        await asyncio.gather(*(one(c) for c in cases))
    finally:
        await engine.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
