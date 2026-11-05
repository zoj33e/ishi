"""Belt exams Orange -> Brown (M8): unlock rules, puzzles then best of 3."""

from __future__ import annotations

from ishi.play.progression import (
    ExamRecord,
    belt_exam_available,
    belt_exam_games_left,
    belt_exam_outcome,
    belt_exam_phase,
)


def test_belt_exam_unlock() -> None:
    assert belt_exam_available("orange", 21.5, 20.0, 5, [])
    assert not belt_exam_available("orange", 22.5, 20.0, 5, [])  # more than 2 stones away
    assert not belt_exam_available("orange", 19.0, 20.0, 4, [])  # too few games
    assert not belt_exam_available("orange", None, 20.0, 9, [])  # no estimate yet
    assert not belt_exam_available("brown", 5.0, None, 9, [])  # Black is post-MVP
    assert not belt_exam_available("orange", 19.0, 20.0, 9, [ExamRecord("in_progress", 0)])
    failed = [ExamRecord("failed", 2)]
    assert not belt_exam_available("orange", 19.0, 20.0, 9, failed)
    assert belt_exam_available("orange", 19.0, 20.0, 9, [ExamRecord("failed", 3)])


def test_belt_exam_outcome_and_phase() -> None:
    open_ = [None] * 12
    assert belt_exam_outcome(open_, 0, 0) == "in_progress"
    assert belt_exam_phase(open_, "in_progress") == "puzzles"
    two_wrong = [False, False] + [True] * 10
    assert belt_exam_outcome(two_wrong, 0, 0) == "in_progress"
    assert belt_exam_phase(two_wrong, "in_progress") == "games"
    assert belt_exam_outcome([False] * 3 + [None] * 9, 0, 0) == "failed"  # 10/12 out of reach
    assert belt_exam_outcome(two_wrong, 2, 1) == "passed"
    assert belt_exam_outcome(two_wrong, 1, 2) == "failed"
    assert belt_exam_phase(two_wrong, "passed") == "done"


def test_games_left_counts_the_wait_after_a_failed_exam() -> None:
    assert belt_exam_games_left(2, []) == 3  # 5 games since the belt
    assert belt_exam_games_left(9, []) == 0
    assert belt_exam_games_left(9, [ExamRecord("failed", 1)]) == 2  # 3 games after a fail
    assert belt_exam_games_left(9, [ExamRecord("failed", 4)]) == 0
