"""Nudge narration (M7): every golden positive, asked as a nudge in both languages, passes the
validator and never shows a correct move."""

from __future__ import annotations

from typing import Literal

import pytest

from ishi.teacher.templates import render
from ishi.teacher.validator import validate
from ishi.why.detectors import DETECTORS
from ishi.why.fact_package import learner_info, nudge_package
from ishi.why.review import MoveReview
from tests.teacher.conftest import POSITIVE_CASES
from tests.why.golden import GOLDEN, load_case

DETECT = dict(DETECTORS)


@pytest.mark.parametrize("locale", ["en", "th"])
@pytest.mark.parametrize("case_id", POSITIVE_CASES)
def test_nudge_never_reveals_the_move(case_id: str, locale: Literal["th", "en"]) -> None:
    case = load_case(GOLDEN / case_id)
    ctx = case.ctx
    hit = DETECT[case.concept](ctx)
    assert hit is not None
    review = MoveReview(17, ctx.gtp(ctx.move), ctx.points_lost, hit, ctx)
    pkg = nudge_package(review, hit, locale=locale, learner=learner_info("green", None))
    assert pkg.move_number is None and not pkg.follow_up_line
    n = render(pkg)
    validate(n.model_dump_json(), pkg)  # raises Rejected (incl. reveals_answer)
    assert n.marks == []
    shown = " ".join(n.texts())
    assert not any(m in shown for m in hit.correct_moves)
    assert n.question and len(n.hints) == 2
