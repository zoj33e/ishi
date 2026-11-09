"""Placement test (D-068): pure rules."""

from __future__ import annotations

from ishi.play.progression import placement_available, placement_belt, placement_outcome


def test_placement_available_once_from_white() -> None:
    assert placement_available("white", 0, False)
    assert not placement_available("white", 1, False)  # only once
    assert not placement_available("white", 0, True)  # another exam under way
    assert not placement_available("yellow", 0, False)


def test_placement_outcome_and_belt() -> None:
    open_ = [None] * 8
    assert placement_outcome(open_, 0, 0) == "in_progress"
    two_wrong = [False, False] + [True] * 6
    assert placement_outcome(two_wrong, 0, 0) == "in_progress"  # 6 of 8: on to the game
    assert placement_outcome([False, False, False] + [None] * 5, 0, 0) == "failed"
    assert placement_outcome(two_wrong, 1, 0) == "passed"
    assert placement_outcome(two_wrong, 0, 1) == "passed"
    assert placement_belt("in_progress", 0) is None
    assert placement_belt("failed", 0) == "white"
    assert placement_belt("passed", 0) == "yellow"
    assert placement_belt("passed", 1) == "orange"
