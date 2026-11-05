"""C6 group_death: a learner group of 3+ stones KataGo thought alive before the move is dead after
it. The key point is the vital point: KataGo's best candidate (in the best set) near the group that
keeps it alive.
A group saved only by a move far away (a tempo elsewhere) is not a local lesson: no hit."""

from __future__ import annotations

from ishi.rules.coords import Point
from ishi.why.context import ConceptHit, MoveContext
from ishi.why.facts import eye_facts

MIN_POINTS_LOST = 4.0
MIN_SIZE = 3
ALIVE_BEFORE = 0.3
DEAD_AFTER = -0.6
NEAR = 2  # the vital point is at most this many lines from a stone of the group

CONCEPT = "group_death"


def detect(ctx: MoveContext) -> ConceptHit | None:
    if ctx.points_lost < MIN_POINTS_LOST:
        return None
    found = []
    for g in ctx.board_before.groups(ctx.learner):
        if len(g.stones) < MIN_SIZE:
            continue
        if ctx.ownership(g.stones, ctx.before.ownership) < ALIVE_BEFORE:
            continue
        remaining = frozenset(s for s in g.stones if ctx.board_after[s] is ctx.learner)
        if remaining and ctx.ownership(remaining, ctx.after.ownership) > DEAD_AFTER:
            continue
        found.append(g)
    if not found:
        return None
    g = max(found, key=lambda g: len(g.stones))
    infos = sorted(ctx.before.moveInfos, key=lambda m: m.order)
    alive_moves = [
        m.move
        for m in infos
        if m.move in ctx.best_moves
        and _near(ctx.point(m.move), g.stones)
        and ctx.ownership(g.stones, m.ownership) >= ALIVE_BEFORE
    ]
    if not alive_moves:
        return None
    vital = alive_moves[0]
    stone = next(iter(g.stones))
    after_chain = ctx.board_after.group_at(stone) if ctx.board_after[stone] is ctx.learner else None
    eyes_after = len(eye_facts(ctx.board_after, after_chain).true_eyes) if after_chain else 0
    return ConceptHit(
        CONCEPT,
        ctx.points_lost,
        {"vital_point": vital},
        [g.stones],
        {
            "group": ctx.gtps(g.stones),
            "vital_point": vital,
            "eyes_before": len(eye_facts(ctx.board_before, g).true_eyes),
            "eyes_after": eyes_after,
        },
        alive_moves,
    )


def _near(p: Point | None, stones: frozenset[Point]) -> bool:
    return p is not None and any(max(abs(p.x - s.x), abs(p.y - s.y)) <= NEAR for s in stones)
