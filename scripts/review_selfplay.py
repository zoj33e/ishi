"""M4 review run: bot-vs-bot 9x9 games, a weak bot standing in for the learner (D-037), every
position analyzed, every learner move run through the Why Engine. Writes a markdown report for
manual review and saves each game (SGF + analyses) so hits can become golden cases.

Usage (from apps/api):
    uv run python ../../scripts/review_selfplay.py --games 10 --out ../../data/review/run1
    uv run python ../../scripts/review_selfplay.py --export ../../data/review/run1/g03 17 \
        tests/golden/missed_capture/mined_g03_m17
    uv run python ../../scripts/review_selfplay.py --report ../../data/review/run1  # re-review
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

from ishi.bots.humansl_bot import profile_for, rank_label
from ishi.config import get_settings
from ishi.engine.katago_process import KataGoProcess
from ishi.engine.models import AnalysisResponse
from ishi.engine.queries import top_move
from ishi.play.analysis import analyze_positions
from ishi.play.selfplay import self_play
from ishi.rules.board import Color
from ishi.rules.coords import GTP_COLUMNS, Point, point_to_gtp
from ishi.rules.game import GameState, new_game, play
from ishi.rules.sgf import parse_sgf, to_sgf
from ishi.why.review import MoveReview, review_moves

CONCURRENCY = 4


def diagram(state: GameState, marks: dict[str, str]) -> str:
    """ASCII board, top row first; `marks` maps GTP -> one-char marker drawn on empty points."""
    size = state.size
    out = []
    for y, row in enumerate(state.board.to_rows()):
        cells = [marks.get(point_to_gtp(Point(x, y), size), ch) for x, ch in enumerate(row)]
        out.append(f"{size - y} " + " ".join(cells))
    out.append("  " + " ".join(GTP_COLUMNS[:size]))
    return "\n".join(out)


def describe(game_no: int, r: MoveReview) -> str:
    hit = r.hit
    assert hit is not None
    ctx = r.ctx
    marks = {v: "!" for v in hit.key_points.values() if v and v != r.move}
    if r.move != "pass":
        marks[r.move] = "*"
    top = top_move(ctx.before)
    reply = top_move(ctx.after)
    name = hit.concept_id + (f"/{hit.variant}" if hit.variant else "")
    lines = [
        f"### g{game_no:02d} move {r.number}: {name}",
        f"- learner ({ctx.learner.name.lower()}) played **{r.move}**, lost {r.points_lost:.1f} pts;"
        f" KataGo best {top.move} (pv {' '.join(top.pv[:5])});"
        f" best set {', '.join(ctx.best_moves)}",
        f"- opponent's best reply {reply.move} (pv {' '.join(reply.pv[:5])})",
        f"- key points {hit.key_points}; correct {hit.correct_moves}; secondary {hit.secondary}",
        f"- evidence {json.dumps(hit.evidence)}",
        "- verdict: _todo_",
        "",
        "```",
        diagram(ctx.state_before, marks),
        "```",
        "",
    ]
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> None:
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    engine = KataGoProcess(get_settings().katago_command())
    await engine.start()
    learner, bot = profile_for(args.learner), profile_for(args.bot)
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(i: int) -> tuple[int, GameState, dict[int, AnalysisResponse]]:
        async with sem:
            r = await self_play(
                engine, learner, bot, random.Random(args.seed * 1000 + i), gid=f"rv{i}"
            )
        async with sem:
            analyses = await analyze_positions(
                engine, r.state, range(r.state.move_number + 1), qid=f"rv{i}"
            )
        d = out / f"g{i:02d}"
        d.mkdir(exist_ok=True)
        (d / "game.sgf").write_text(to_sgf(r.state, result=r.result) + "\n", encoding="utf-8")
        (d / "analyses.json").write_text(
            json.dumps({t: a.model_dump(exclude_none=True) for t, a in sorted(analyses.items())}),
            encoding="utf-8",
        )
        print(f"g{i:02d}: {r.result} in {r.moves} moves", flush=True)
        return i, r.state, analyses

    try:
        games = await asyncio.gather(*(one(i) for i in range(args.games)))
    finally:
        await engine.stop()

    title = (
        f"# M4 review run: learner {rank_label(args.learner)} (Black) vs bot {rank_label(args.bot)}"
    )
    write_report(out, title, f"{args.games} games, seed {args.seed}", list(games))


def write_report(
    out: Path,
    title: str,
    subtitle: str,
    games: list[tuple[int, GameState, dict[int, AnalysisResponse]]],
) -> None:
    sections, counts, total_moves = [], {}, 0
    for i, state, analyses in games:
        reviews = review_moves(state, analyses, Color.BLACK)
        total_moves += len(reviews)
        for r in reviews:
            if r.hit is None:
                continue
            counts[r.hit.concept_id] = counts.get(r.hit.concept_id, 0) + 1
            sections.append(describe(i, r))
    header = [
        title,
        "",
        f"{subtitle}, {total_moves} learner moves reviewed.",
        f"Hits: {json.dumps(counts)}",
        "",
        "Legend: `*` the learner's move, `!` the hit's key point.",
        "",
    ]
    (out / "report.md").write_text("\n".join(header + sections), encoding="utf-8")
    print(f"{sum(counts.values())} hits {counts}; report at {out / 'report.md'}")


def rereport(out: Path) -> None:
    """Rebuild report.md from the saved games, without the engine (after a detector change)."""
    old = (out / "report.md").read_text(encoding="utf-8").splitlines()
    title, subtitle = old[0], ", ".join(old[2].split(", ")[:2])
    games = []
    for d in sorted(out.glob("g[0-9][0-9]")):
        game = parse_sgf((d / "game.sgf").read_text(encoding="utf-8"))
        state = new_game(game.size, game.komi)
        for _, point in game.moves:
            state = play(state, point)
        raw = json.loads((d / "analyses.json").read_text(encoding="utf-8"))
        analyses = {int(t): AnalysisResponse.model_validate(a) for t, a in raw.items()}
        games.append((int(d.name[1:]), state, analyses))
    write_report(out, title, subtitle, games)


def export(game_dir: Path, number: int, case: Path) -> None:
    """Write a golden case from move `number` of a saved review game."""
    game = parse_sgf((game_dir / "game.sgf").read_text(encoding="utf-8"))
    analyses = json.loads((game_dir / "analyses.json").read_text(encoding="utf-8"))
    state = new_game(game.size, game.komi)
    for _, point in game.moves[:number]:
        state = play(state, point)
    case.mkdir(parents=True, exist_ok=True)
    (case / "position.sgf").write_text(to_sgf(state) + "\n", encoding="utf-8")
    for name, turn in (("analysis_before.json", number - 1), ("analysis_after.json", number)):
        (case / name).write_text(json.dumps(analyses[str(turn)], indent=1) + "\n", encoding="utf-8")
    print(f"exported {case}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=10)
    ap.add_argument("--learner", type=float, default=26)
    ap.add_argument("--bot", type=float, default=22)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path("../../data/review/run"))
    ap.add_argument("--export", nargs=3, metavar=("GAME_DIR", "MOVE", "CASE_DIR"))
    ap.add_argument("--report", type=Path, metavar="RUN_DIR")
    args = ap.parse_args()
    if args.report:
        rereport(args.report)
        return
    if args.export:
        game_dir, number, case = args.export
        export(Path(game_dir), int(number), Path(case))
        return
    asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
