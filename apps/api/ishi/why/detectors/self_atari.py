"""C3 self_atari: the learner's move left its own chain with one liberty and the opponent can
take it. Throw-ins and snapbacks that KataGo rates fine (pointsLost < 1) are excluded."""

from __future__ import annotations

from ishi.why.context import ConceptHit, MoveContext

MIN_POINTS_LOST = 2.0
SACRIFICE_OK = 1.0  # below this the "self-atari" is a fine sacrifice

CONCEPT = "self_atari"


def detect(ctx: MoveContext) -> ConceptHit | None:
    if ctx.move is None or ctx.points_lost < SACRIFICE_OK:
        return None
    chain = ctx.board_after.group_at(ctx.move)
    if chain is None or len(chain.liberties) != 1:
        return None
    (last,) = chain.liberties
    capture_legal = last != ctx.state_after.ko_point
    reply_captures = ctx.point(ctx.top_after.move) == last
    if not (reply_captures or (capture_legal and ctx.points_lost >= MIN_POINTS_LOST)):
        return None
    return ConceptHit(
        CONCEPT,
        ctx.points_lost,
        {"last_liberty": ctx.gtp(last), "played_move": ctx.gtp(ctx.move)},
        [chain.stones],
        {"group": ctx.gtps(chain.stones), "last_liberty": ctx.gtp(last), "size": len(chain.stones)},
        list(ctx.best_moves),
    )
