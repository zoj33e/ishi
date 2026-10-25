"""Find a correct answer for any lesson task with the grader itself (test helper)."""

from typing import Any

from ishi.rules.coords import Point, point_to_gtp
from ishi.school.content import Lesson, Task
from ishi.school.grading import (
    Answer,
    board_size,
    expected_choice,
    expected_count,
    expected_points,
    grade,
    initial_state,
)


def solve(lesson: Lesson, task: Task) -> list[dict[str, Any]]:
    """Request bodies that complete the task (one per step for play tasks)."""
    state = initial_state(lesson, task.setup)
    if task.kind == "count":
        assert task.count
        return [{"number": expected_count(task.count, state)}]
    if task.kind == "select":
        assert task.select
        want = sorted(expected_points(task.select, state))
        return [{"points": want if task.select.mode == "all" else want[:1]}]
    if task.kind == "choose":
        assert task.choose
        return [{"choice": expected_choice(task.choose, state)}]
    size = board_size(lesson, task.setup)
    cands = ["pass"] + [point_to_gtp(Point(x, y), size) for y in range(size) for x in range(size)]
    moves: list[str] = []
    bodies = []
    for _ in task.steps:
        move = next(c for c in cands if grade(lesson, task, Answer(moves=[*moves, c])).correct)
        moves.append(move)
        bodies.append({"moves": list(moves)})
    return bodies
