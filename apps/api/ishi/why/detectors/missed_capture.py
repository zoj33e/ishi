"""C1 missed_capture: an opponent group could be captured (now, or by a working ladder) and
KataGo agrees capturing was best, but the learner played elsewhere."""

from __future__ import annotations

from ishi.rules.board import Group
from ishi.rules.coords import Point
from ishi.why.context import ConceptHit, MoveContext
from ishi.why.facts import capturable_groups
from ishi.why.ladder import read_ladder

MIN_POINTS_LOST = 2.0

CONCEPT = "missed_capture"


def _ladder_moves(ctx: MoveContext, group: Group) -> list[Point]:
    """Atari moves on a 2-liberty group that start a working ladder."""
    out = []
    for lib in sorted(group.liberties):
        if lib == ctx.state_before.ko_point:
            continue
        after, _ = ctx.board_before.place(lib, ctx.learner)
        mine = after.group_at(lib)
        chased = after.group_at(next(iter(group.stones)))
        if not mine or not mine.liberties or chased is None or len(chased.liberties) != 1:
            continue
        if read_ladder(after, next(iter(group.stones))).works:
            out.append(lib)
    return out


def detect(ctx: MoveContext) -> ConceptHit | None:
    if ctx.points_lost < MIN_POINTS_LOST:
        return None
    best = set(ctx.best_points)
    candidates: list[tuple[Group, list[Point], bool]] = [
        (g, [p], False)
        for g, p in capturable_groups(ctx.board_before, ctx.learner, ctx.state_before.ko_point)
    ]
    for g in ctx.board_before.groups(ctx.learner.opponent):
        if len(g.liberties) == 2:
            moves = _ladder_moves(ctx, g)
            if moves:
                candidates.append((g, moves, True))

    found: list[tuple[Group, list[Point], bool]] = []
    for g, moves, via_ladder in candidates:
        good = [m for m in moves if m in best]
        if not good:
            continue
        if g.stones & ctx.captured:  # the learner did capture it
            continue
        if via_ladder and ctx.move in moves:  # the learner started the ladder
            continue
        found.append((g, good, via_ladder))
    if not found:
        return None
    # The biggest target; a direct capture beats a ladder of the same size.
    g, good, via_ladder = max(found, key=lambda f: (len(f[0].stones), not f[2]))
    point = good[0]
    return ConceptHit(
        CONCEPT,
        ctx.points_lost,
        {"capture_point": ctx.gtp(point)},
        [g.stones],
        {
            "target_group": ctx.gtps(g.stones),
            "target_size": len(g.stones),
            "capture_point": ctx.gtp(point),
            "via_ladder": via_ladder,
        },
        [ctx.gtp(m) for m in good],
    )
