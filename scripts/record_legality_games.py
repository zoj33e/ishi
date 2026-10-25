"""Record random games played through KataGo, with KataGo's legal-move mask at every turn.

The mask comes from the raw policy (`-1` = illegal under the rules we send), so
`tests/rules/test_katago_legality.py` can check that our rules engine agrees with KataGo
on every point of every position, without running the engine.

Moves are sampled half from KataGo's policy and half uniformly from KataGo's legal set, with
the occasional pass, so games contain plenty of captures, ko fights and suicide points.

Usage (needs a configured engine, see scripts/setup_engine.ps1):
    uv run --project apps/api python scripts/record_legality_games.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from ishi.config import get_settings  # noqa: E402
from ishi.engine.katago_process import KataGoProcess  # noqa: E402
from ishi.engine.models import AnalysisQuery  # noqa: E402
from ishi.rules.coords import index_to_point, point_to_gtp  # noqa: E402

OUT_DIR = ROOT / "apps" / "api" / "tests" / "fixtures" / "legality"
# (board size, number of games, move cap)
PLAN = [(9, 14, 220), (7, 3, 140), (13, 3, 320)]
KOMI = 7


async def record_game(engine: KataGoProcess, size: int, cap: int, rng: random.Random, name: str):
    moves: list[list[str]] = []
    masks: list[str] = []
    color = "B"
    passes = 0
    while passes < 2 and len(moves) < cap:
        q = AnalysisQuery(
            id=f"{name}-t{len(moves)}",
            moves=[(c, m) for c, m in moves],
            boardXSize=size,
            boardYSize=size,
            komi=KOMI,
            maxVisits=1,
            includePolicy=True,
        )
        [resp] = await engine.analyze(q, timeout=30)
        assert resp.policy is not None
        board_policy = resp.policy[: size * size]
        masks.append("".join("1" if v >= 0 else "0" for v in board_policy))
        legal = [i for i, v in enumerate(board_policy) if v >= 0]

        if not legal or (passes == 0 and len(moves) > 10 and rng.random() < 0.03):
            move = "pass"
        elif rng.random() < 0.5:
            weights = [board_policy[i] for i in legal]
            move = point_to_gtp(index_to_point(rng.choices(legal, weights)[0], size), size)
        else:
            move = point_to_gtp(index_to_point(rng.choice(legal), size), size)
        passes = passes + 1 if move == "pass" else 0
        moves.append([color, move])
        color = "W" if color == "B" else "B"
    return {
        "size": size,
        "komi": KOMI,
        "rules": "ko SIMPLE, scoring AREA, suicide false",
        "moves": moves,
        # masks[t] = legal points for the player to move before moves[t], row-major from top-left
        "legal_masks": masks,
    }


async def main(seed: int) -> None:
    settings = get_settings()
    if not settings.katago_configured:
        sys.exit("KataGo not configured; run scripts/setup_engine.ps1")
    engine = KataGoProcess(settings.katago_command(), auto_restart=False)
    await engine.start()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    n = 0
    try:
        for size, games, cap in PLAN:
            for _ in range(games):
                n += 1
                name = f"game{n:02d}_{size}x{size}"
                t0 = time.perf_counter()
                game = await record_game(engine, size, cap, rng, name)
                game["katago_version"] = engine.version
                game["seed"] = seed
                path = OUT_DIR / f"{name}.json"
                path.write_text(json.dumps(game, separators=(",", ":")), encoding="utf-8")
                print(f"{name}: {len(game['moves'])} moves in {time.perf_counter() - t0:.1f}s")
    finally:
        await engine.stop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261025)
    asyncio.run(main(ap.parse_args().seed))
