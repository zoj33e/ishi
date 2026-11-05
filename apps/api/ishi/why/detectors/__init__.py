"""Concept detectors C1-C6 and the per-move verdict (05-why-engine)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from ishi.why.context import ConceptHit, MoveContext
from ishi.why.detectors import (
    cut_disconnect,
    group_death,
    ignored_atari,
    ladder,
    missed_capture,
    self_atari,
)

# Most specific first: when several fire on one move, the first is the lesson, the rest secondary.
DETECTORS: list[tuple[str, Callable[[MoveContext], ConceptHit | None]]] = [
    (missed_capture.CONCEPT, missed_capture.detect),
    (ignored_atari.CONCEPT, ignored_atari.detect),
    (self_atari.CONCEPT, self_atari.detect),
    (ladder.CONCEPT, ladder.detect),
    (cut_disconnect.CONCEPT, cut_disconnect.detect),
    (group_death.CONCEPT, group_death.detect),
]
CONCEPTS = [c for c, _ in DETECTORS]

UNEXPLAINED = "unexplained"
UNEXPLAINED_POINTS = 5.0


def run_detectors(ctx: MoveContext) -> list[ConceptHit]:
    return [hit for _, detect in DETECTORS if (hit := detect(ctx)) is not None]


def classify(ctx: MoveContext) -> ConceptHit | None:
    """The move's main concept hit (others as `secondary`), `unexplained` for a big mistake no
    detector explains, or None."""
    hits = run_detectors(ctx)
    if hits:
        return replace(hits[0], secondary=[h.concept_id for h in hits[1:]])
    if ctx.points_lost >= UNEXPLAINED_POINTS:
        return ConceptHit(
            UNEXPLAINED,
            ctx.points_lost,
            {},
            [],
            {"played_move": ctx.gtp(ctx.move)},
            list(ctx.best_moves),
        )
    return None
