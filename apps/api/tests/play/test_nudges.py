"""Nudge decisions (M7) on golden positions with recorded KataGo analyses."""

from __future__ import annotations

import pytest

from ishi.play import nudges
from ishi.rules.coords import gtp_to_point
from tests.teacher.conftest import POSITIVE_CASES
from tests.why.golden import GOLDEN, load_case


def test_threshold() -> None:
    assert nudges.threshold([]) == 4.0
    assert nudges.threshold([0.5, 1.0, 1.5]) == 4.0  # max(4, 2 x median)
    assert nudges.threshold([1.0, 3.0, 5.0, 9.0]) == 8.0


@pytest.mark.parametrize("case_id", POSITIVE_CASES)
def test_golden_mistakes_nudge_when_big_enough_and_unlocked(case_id: str) -> None:
    case = load_case(GOLDEN / case_id)
    ctx = case.ctx
    lost = ctx.points_lost
    found = nudges.decide(ctx, 17, "black", limit=lost, pf=None)  # every concept open
    assert found is not None
    review, hit = found
    # the main concept of the whole classifier (a golden case may be its secondary concept)
    assert case.concept in {hit.concept_id, *hit.secondary} and review.move == ctx.gtp(ctx.move)
    assert nudges.decide(ctx, 17, "black", limit=lost + 0.1, pf=None) is None  # too small
    assert nudges.decide(ctx, 17, "white", limit=lost, pf=None) is None  # nothing unlocked yet
    assert nudges.decide(ctx, 17, "black", limit=lost, pf=0.01) is None  # rank filter: too hard


@pytest.mark.parametrize("answer", ["A1", "E5", "J9", "E1", "C7"])
def test_focus_area_contains_the_answer_but_is_not_it(answer: str) -> None:
    focus = nudges.focus_area([answer], 9)
    assert focus is not None and focus != answer
    a, f = gtp_to_point(answer, 9), gtp_to_point(focus, 9)
    assert a is not None and f is not None
    assert max(abs(a.x - f.x), abs(a.y - f.y)) == 1  # inside the 3x3 area
