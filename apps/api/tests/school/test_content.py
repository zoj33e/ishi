"""Every lesson must load, be solvable, and agree with the rules engine (docs/11-testing.md)."""

import pytest

from ishi.rules.coords import Point, gtp_to_point, point_to_gtp
from ishi.rules.game import Legality, check_move, play
from ishi.school.content import Lesson, PlaceAny, Setup, Task, load_lessons
from ishi.school.grading import (
    Answer,
    board_size,
    expected_choice,
    expected_count,
    expected_points,
    grade,
    initial_state,
)

LESSONS = load_lessons()
TASKS = [(lesson, task) for lesson in LESSONS for task in lesson.tasks]


def _ids(item: tuple[Lesson, Task]) -> str:
    return f"{item[0].id}-{item[1].id}"


def test_ten_lessons_in_order() -> None:
    assert [lesson.id for lesson in LESSONS] == [f"R{i}" for i in range(1, 11)]
    assert [lesson.order for lesson in LESSONS] == list(range(1, 11))


def _check_setup(lesson: Lesson, setup: Setup) -> None:
    size = board_size(lesson, setup)
    pts = [*setup.black, *setup.white]
    for p in pts:
        assert gtp_to_point(p, size) is not None
    assert len(set(pts)) == len(pts), "duplicate stones in setup"
    initial_state(lesson, setup)  # moves must be legal


@pytest.mark.parametrize("lesson", LESSONS, ids=lambda lesson: lesson.id)
def test_demo_is_valid(lesson: Lesson) -> None:
    _check_setup(lesson, lesson.demo.setup)
    state = initial_state(lesson, lesson.demo.setup)
    size = state.size
    for frame in lesson.demo.frames:
        if frame.move:
            point = gtp_to_point(frame.move, size)
            assert check_move(state, point) is Legality.OK, frame.move
            state = play(state, point)
        for mark in frame.marks:
            assert gtp_to_point(mark.point, size) is not None


@pytest.mark.parametrize("item", TASKS, ids=_ids)
def test_task_setup_is_valid(item: tuple[Lesson, Task]) -> None:
    lesson, task = item
    _check_setup(lesson, task.setup)


def _candidates(size: int) -> list[str]:
    return ["pass"] + [point_to_gtp(Point(x, y), size) for y in range(size) for x in range(size)]


@pytest.mark.parametrize("item", [t for t in TASKS if t[1].kind == "play"], ids=_ids)
def test_play_task_is_solvable_and_not_trivial(item: tuple[Lesson, Task]) -> None:
    lesson, task = item
    size = board_size(lesson, task.setup)
    solution: list[str] = []
    for i, step in enumerate(task.steps):
        correct = []
        tried = 0
        for cand in _candidates(size):
            g = grade(lesson, task, Answer(moves=[*solution, cand]))
            if g.feedback_key.startswith("school.feedback.illegal"):
                continue
            tried += 1
            if g.correct:
                correct.append((cand, g))
        assert correct, f"step {i} has no solution"
        if not isinstance(step.goal, PlaceAny):
            assert len(correct) < tried, f"step {i}: every legal move is correct"
        cand, g = correct[0]
        last = i == len(task.steps) - 1
        assert g.done is last
        if not last:
            assert g.reply is not None, f"step {i} needs a scripted reply"
        solution.append(cand)


@pytest.mark.parametrize("item", [t for t in TASKS if t[1].kind == "count"], ids=_ids)
def test_count_expect_matches_engine(item: tuple[Lesson, Task]) -> None:
    lesson, task = item
    assert task.count is not None
    n = expected_count(task.count, initial_state(lesson, task.setup))
    if task.expect is not None:
        assert n == task.expect
    assert grade(lesson, task, Answer(number=n)).correct
    assert not grade(lesson, task, Answer(number=n + 1)).correct


@pytest.mark.parametrize("item", [t for t in TASKS if t[1].kind == "select"], ids=_ids)
def test_select_has_answer(item: tuple[Lesson, Task]) -> None:
    lesson, task = item
    assert task.select is not None
    want = expected_points(task.select, initial_state(lesson, task.setup))
    assert want, "nothing to select"
    if task.expect is not None:
        assert want == {task.expect}
    pick = sorted(want) if task.select.mode == "all" else [sorted(want)[0]]
    assert grade(lesson, task, Answer(points=pick)).correct


@pytest.mark.parametrize("item", [t for t in TASKS if t[1].kind == "choose"], ids=_ids)
def test_choose_expect_matches_engine(item: tuple[Lesson, Task]) -> None:
    lesson, task = item
    assert task.choose is not None
    choice = expected_choice(task.choose, initial_state(lesson, task.setup))
    if task.expect is not None:
        assert choice == task.expect
    assert grade(lesson, task, Answer(choice=choice)).correct


@pytest.mark.parametrize("item", TASKS, ids=_ids)
def test_text_is_bilingual(item: tuple[Lesson, Task]) -> None:
    _, task = item
    for text in (task.prompt, task.hint, task.success):
        assert text.en.strip() and text.th.strip()


def test_r8_false_eye_spans_two_chains() -> None:
    lesson = next(lesson for lesson in LESSONS if lesson.id == "R8")
    task = lesson.task("t3")
    assert task is not None and task.select is not None
    assert expected_points(task.select, initial_state(lesson, task.setup)) == {"C1"}
