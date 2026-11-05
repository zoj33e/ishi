"""C4 ladder, two variants:
- broken_ladder_chase: the learner's atari starts a ladder that doesn't work;
- ran_into_ladder: the learner extended a group in atari into a working ladder.
A missed working ladder is C1 (missed_capture with via_ladder)."""

from __future__ import annotations

from ishi.why.context import ConceptHit, MoveContext
from ishi.why.facts import groups_in_atari
from ishi.why.ladder import ladder_start, read_ladder

MIN_POINTS_LOST = 2.0
MIN_CHASE_PLIES = 3  # the defender runs and can be put in atari again: it really is a ladder

CONCEPT = "ladder"


def _broken_chase(ctx: MoveContext) -> ConceptHit | None:
    move = ctx.move
    assert move is not None
    board = ctx.board_after
    for n in board.neighbors(move):
        if board[n] is not ctx.learner.opponent:
            continue
        chain = board.group_at(n)
        if chain is None or len(chain.liberties) != 1:
            continue
        was = ctx.board_before.group_at(n)
        if was is None or len(was.liberties) != 2:  # the learner's move made the atari
            continue
        result = read_ladder(board, n)
        if result.works or len(result.path) < MIN_CHASE_PLIES:
            continue
        keys = {"atari_move": ctx.gtp(move)}
        if result.breaker:
            keys["breaker"] = ctx.gtp(result.breaker)
        return ConceptHit(
            CONCEPT,
            ctx.points_lost,
            keys,
            [chain.stones],
            {
                "path": [ctx.gtp(p) for p in result.path],
                "breaker": ctx.gtp(result.breaker) if result.breaker else None,
            },
            list(ctx.best_moves),
            variant="broken_ladder_chase",
        )
    return None


def _ran_into_ladder(ctx: MoveContext) -> ConceptHit | None:
    move = ctx.move
    assert move is not None
    for g in groups_in_atari(ctx.board_before, ctx.learner):
        if move not in g.liberties:
            continue
        chain = ctx.board_after.group_at(move)
        if chain is None or len(chain.liberties) != 2:
            continue
        start = ladder_start(ctx.board_after, move)
        if start is None:
            continue
        return ConceptHit(
            CONCEPT,
            ctx.points_lost,
            {"escape_move": ctx.gtp(move), "ladder_start": ctx.gtp(start.path[0])},
            [chain.stones],
            {"path": [ctx.gtp(p) for p in start.path], "breaker": None},
            list(ctx.best_moves),
            variant="ran_into_ladder",
        )
    return None


def detect(ctx: MoveContext) -> ConceptHit | None:
    if ctx.move is None or ctx.points_lost < MIN_POINTS_LOST:
        return None
    return _ran_into_ladder(ctx) or _broken_chase(ctx)
