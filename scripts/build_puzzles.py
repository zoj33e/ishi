"""Build the Shape Gym seed set (M6): KataGo's answer set for every authored puzzle.

Usage (from apps/api):
    uv run python ../../scripts/build_puzzles.py           # all -> content/puzzles/seed.json
    uv run python ../../scripts/build_puzzles.py mc01 ld03 # check some, don't write

For each puzzle in `content/puzzles/<concept>.yaml` the rules decide which first moves solve it
(captures, saves, connects - `ishi.gym.puzzles.resolves`); KataGo then analyzes the position with
the side to move limited to those moves, and the correct set is every solving move within 1.0 point
of the best solving move (02-curriculum's "within 1.0 point" rule, D-051). Life (group_death) is
judged by KataGo's ownership after each move in the puzzle's region. The authored answer must be
in the set, or the build fails and names the puzzle.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from ishi.config import get_settings
from ishi.engine.katago_process import KataGoProcess
from ishi.engine.queries import for_player, puzzle_query
from ishi.gym.puzzles import SEED_FILE, SeedPuzzle, load_authored, resolves
from ishi.rules.board import Color
from ishi.rules.coords import gtp_to_point, point_to_gtp, point_to_index
from ishi.rules.game import Legality, check_move, play

BUILD_VISITS = 1500
LINE_PLIES = 6
LIMIT = asyncio.Semaphore(4)
MIN_VISITS = 20  # a move's score needs this many visits to be trusted
LOSS = 1.0
LIFE_VISITS = 400
ALIVE = 0.5  # group_death: the target group's ownership for the learner after the move


async def _lives(engine: KataGoProcess, pz: SeedPuzzle, move: str, stones: list) -> bool:
    """After `move`, the opponent to play locally: does the target group stay the learner's?"""
    p = gtp_to_point(move, pz.size)
    assert p is not None
    if check_move(pz.state(), p) is not Legality.OK:
        return False
    after = play(pz.state(), p)
    query = puzzle_query(
        f"seed-{pz.id}-{move}", after, pz.region(), max_visits=LIFE_VISITS, moves_ownership=True
    )
    async with LIMIT:
        (resp,) = await engine.analyze(query, timeout=120)
    assert resp.ownership is not None
    mine = [for_player(resp.ownership[point_to_index(s, pz.size)], pz.to_move) for s in stones]
    return min(mine) >= ALIVE


async def build_one(engine: KataGoProcess, pz: SeedPuzzle) -> tuple[dict | None, str | None]:
    death = pz.concept_id == "group_death"
    me = pz.to_move
    if death:  # moves in or next to the group that leave it alive (KataGo's ownership)
        assert pz.target
        target = gtp_to_point(pz.target, pz.size)
        group = pz.board.group_at(target) if target else None
        assert group is not None
        near = [
            m
            for m in pz.region()
            if any(
                max(abs(q.x - s.x), abs(q.y - s.y)) <= 1
                for q in [gtp_to_point(m, pz.size)]
                if q is not None
                for s in group.stones
            )
        ]
        stones = list(group.stones)
        lives = await asyncio.gather(*(_lives(engine, pz, m, stones) for m in near))
        candidates = [m for m, ok in zip(near, lives, strict=True) if ok]
    else:
        candidates = [m for m in pz.region() if resolves(pz, m)]
    if not candidates:
        return None, f"{pz.id}: no move solves it"
    query = puzzle_query(f"seed-{pz.id}", pz.state(), candidates, max_visits=BUILD_VISITS)
    async with LIMIT:
        (resp,) = await engine.analyze(query, timeout=120)
    infos = {m.move: m for m in resp.moveInfos if m.visits >= MIN_VISITS}
    if not infos:
        return None, f"{pz.id}: KataGo found no solving move (candidates {candidates})"
    top = max(for_player(i.scoreLead, me) for i in infos.values())
    correct = sorted(
        (m for m, i in infos.items() if for_player(i.scoreLead, me) >= top - LOSS),
        key=lambda m: -for_player(infos[m].scoreLead, me),
    )
    if pz.answer not in correct:
        scores = ", ".join(
            f"{m.move} {for_player(m.scoreLead, me):+.1f} ({m.visits}v)"
            for m in sorted(resp.moveInfos, key=lambda m: m.order)[:5]
        )
        return None, f"{pz.id}: {pz.answer} not in {correct} (solving {candidates}; {scores})"
    pv = infos[pz.answer].pv[:LINE_PLIES]
    color = me
    line = []
    for mv in pv:
        line.append(f"{'B' if color is Color.BLACK else 'W'} {mv}")
        color = color.opponent
    size = pz.size
    return {
        "id": pz.id,
        "concept_id": pz.concept_id,
        "board_size": size,
        "setup": {
            "black": [point_to_gtp(p, size) for p in pz.board.stones(Color.BLACK)],
            "white": [point_to_gtp(p, size) for p in pz.board.stones(Color.WHITE)],
            "to_move": "black" if me is Color.BLACK else "white",
            "komi": pz.state().komi,
            "ko_point": None,
            "rules": {},
            "region": pz.region(),
            "target": pz.target,
        },
        "correct_moves": correct,
        "solution_line": line,
        "learner_moves": pz.moves,
    }, None


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="only these puzzles (no seed.json written)")
    args = ap.parse_args()
    puzzles = load_authored()
    ids = [p.id for p in puzzles]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        print(f"duplicate ids: {sorted(dupes)}", file=sys.stderr)
        return 1
    if args.ids:
        puzzles = [p for p in puzzles if p.id in set(args.ids)]
    engine = KataGoProcess(get_settings().katago_command())
    await engine.start()
    try:
        results = await asyncio.gather(*(build_one(engine, p) for p in puzzles))
    finally:
        await engine.stop()
    errors = [e for _, e in results if e]
    for (item, _), pz in zip(results, puzzles, strict=True):
        if item:
            print(f"ok {pz.id:8s} {pz.concept_id:15s} answers {', '.join(item['correct_moves'])}")
    for e in errors:
        print("FAIL", e, file=sys.stderr)
    if errors or args.ids:
        return 1 if errors else 0
    SEED_FILE.write_text(
        json.dumps([item for item, _ in results], indent=1) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(results)} puzzles to {SEED_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
