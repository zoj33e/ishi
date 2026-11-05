"""Golden positions for every detector (11-testing): real KataGo analyses recorded once, so these
run without the engine. Each detector needs >= 5 positives and >= 3 look-alike negatives."""

from collections import Counter

import pytest

from ishi.why.detectors import CONCEPTS, DETECTORS

from .golden import GoldenCase, all_cases

CASES = all_cases()
DETECT = dict(DETECTORS)


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_golden_case(case: GoldenCase) -> None:
    assert case.expected is not None, f"{case.id}: no expected.json"
    hit = DETECT[case.concept](case.ctx)
    if not case.expected["fires"]:
        assert hit is None, f"{case.id} should not fire: {hit}"
        return
    assert hit is not None, f"{case.id} should fire"
    assert hit.concept_id == case.concept
    assert hit.variant == case.expected.get("variant")
    for role, point in case.expected.get("key_points", {}).items():
        assert hit.key_points.get(role) == point, f"{case.id}: {role}"
    for move in case.expected.get("correct_moves", []):
        assert move in hit.correct_moves, f"{case.id}: {move} not among correct moves"


def test_every_detector_has_enough_golden_cases() -> None:
    positives = Counter(c.concept for c in CASES if c.expected and c.expected["fires"])
    negatives = Counter(c.concept for c in CASES if c.expected and not c.expected["fires"])
    for concept in CONCEPTS:
        assert positives[concept] >= 5, f"{concept}: {positives[concept]} positives"
        assert negatives[concept] >= 3, f"{concept}: {negatives[concept]} negatives"
