"""Review a finished game move by move: pointsLost and the detectors' verdict (pure, no I/O)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ishi.engine.models import AnalysisResponse
from ishi.rules.board import Color
from ishi.rules.coords import point_to_gtp
from ishi.rules.game import GameState, new_game, play
from ishi.why.context import ConceptHit, MoveContext
from ishi.why.detectors import classify


@dataclass(frozen=True)
class MoveReview:
    number: int  # 1-based move number
    move: str  # GTP or "pass"
    points_lost: float
    hit: ConceptHit | None  # main concept (secondary inside), "unexplained", or None
    ctx: MoveContext


def review_moves(
    final: GameState, analyses: Mapping[int, AnalysisResponse], learner: Color
) -> list[MoveReview]:
    """Every learner move whose before/after positions are both analyzed.

    `analyses[t]` is the analysis of the position after t moves (0 = start)."""
    if final.initial_board is not None:
        raise ValueError("review_moves needs a game that started from an empty board")
    state = new_game(final.size, final.komi)
    out = []
    for number, m in enumerate(final.moves, start=1):
        before, after = analyses.get(number - 1), analyses.get(number)
        if m.color is learner and before is not None and after is not None:
            ctx = MoveContext(state_before=state, move=m.point, before=before, after=after)
            out.append(
                MoveReview(
                    number, point_to_gtp(m.point, final.size), ctx.points_lost, classify(ctx), ctx
                )
            )
        state = play(state, m.point)
    return out
