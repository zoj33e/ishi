"""Fact packages from the golden cases (real detector output) for teacher tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import pytest

from ishi.why.detectors import DETECTORS
from ishi.why.fact_package import FactPackage, learner_info, mistake_package
from ishi.why.review import MoveReview
from tests.why.golden import GOLDEN, all_cases, load_case

DETECT = dict(DETECTORS)
POSITIVE_CASES = [c.id for c in all_cases() if c.expected and c.expected["fires"]]

MakePackage = Callable[..., FactPackage]


def package_for(
    case_id: str, locale: Literal["th", "en"] = "en", *, new: bool = False, number: int = 17
) -> FactPackage:
    case = load_case(GOLDEN / case_id)
    hit = DETECT[case.concept](case.ctx)
    assert hit is not None
    ctx = case.ctx
    review = MoveReview(number, ctx.gtp(ctx.move), ctx.points_lost, hit, ctx)
    return mistake_package(
        review, hit, locale=locale, learner=learner_info("yellow", None), concept_is_new=new
    )


@pytest.fixture
def make_package() -> MakePackage:
    return package_for
