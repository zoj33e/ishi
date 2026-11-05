"""C5 cut_disconnect: the learner left a cutting point between two of its groups, the opponent's
best answer cuts there, and one of the separated groups suffers for it."""

from __future__ import annotations

from ishi.rules.board import Group
from ishi.rules.coords import Point
from ishi.why.context import ConceptHit, MoveContext
from ishi.why.facts import cutting_points

MIN_POINTS_LOST = 3.0
WEAK_AFTER_CUT = -0.3  # group ownership (learner's side) after the cut
OWNERSHIP_DROP = 0.5

CONCEPT = "cut_disconnect"


def _connects(ctx: MoveContext, move: Point, a: Group, b: Group) -> bool:
    if ctx.board_before[move] is not None:
        return False
    after, _ = ctx.board_before.place(move, ctx.learner)
    chain = after.group_at(next(iter(a.stones)))
    return chain is not None and bool(chain.stones & b.stones)


def _opponent_cuts(ctx: MoveContext) -> list[Point]:
    """Where the opponent's best line cuts: its reply, and its next move in the PV (D-037)."""
    pv = ctx.top_after.pv
    moves = [pv[0]] if pv else [ctx.top_after.move]
    if len(pv) >= 3:
        moves.append(pv[2])
    return [p for p in (ctx.point(m) for m in moves) if p is not None]


def detect(ctx: MoveContext) -> ConceptHit | None:
    if ctx.points_lost < MIN_POINTS_LOST:
        return None
    cuts = cutting_points(ctx.board_before, ctx.learner)
    if not cuts:
        return None
    reply_line = _opponent_cuts(ctx)
    cut_after = ctx.top_after.ownership or ctx.after.ownership
    for p in reply_line:
        groups = cuts.get(p)
        if not groups or ctx.board_after[p] is not None:  # no cut there, or the learner filled it
            continue
        for i, a in enumerate(groups):
            for b in groups[i + 1 :]:
                if a.liberties & b.liberties != {p}:
                    continue
                if ctx.move is not None and _connects(ctx, ctx.move, a, b):
                    continue
                weak = [
                    g
                    for g in (a, b)
                    if ctx.ownership(g.stones, cut_after) < WEAK_AFTER_CUT
                    or ctx.ownership(g.stones, ctx.before.ownership)
                    - ctx.ownership(g.stones, cut_after)
                    >= OWNERSHIP_DROP
                ]
                if not weak:
                    continue
                connect = [m for m in ctx.best_points if _connects(ctx, m, a, b)]
                if not connect:
                    continue
                return ConceptHit(
                    CONCEPT,
                    ctx.points_lost,
                    {"cut_point": ctx.gtp(p), "connect_move": ctx.gtp(connect[0])},
                    [a.stones, b.stones],
                    {
                        "cut_point": ctx.gtp(p),
                        "groups": [ctx.gtps(a.stones), ctx.gtps(b.stones)],
                        "connect_moves": [ctx.gtp(m) for m in connect],
                    },
                    [ctx.gtp(m) for m in connect],
                )
    return None
