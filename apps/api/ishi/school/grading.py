"""Auto-grading of rules-school tasks with the rules engine. Pure functions, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field

from ishi.rules.board import Board, Color
from ishi.rules.coords import Point, gtp_to_point, point_to_gtp
from ishi.rules.game import GameState, Legality, check_move, new_game, play
from ishi.rules.scoring import area_score
from ishi.school.content import (
    Atari,
    Capture,
    ChooseSpec,
    Connect,
    CountSpec,
    Cut,
    Escape,
    Goal,
    Lesson,
    Mark,
    Pass,
    PlaceAny,
    PlaceAt,
    Reply,
    SelectSpec,
    Setup,
    Task,
    TwoEyes,
)
from ishi.why.groups import false_eyes, true_eyes

FB = "school.feedback."


@dataclass(frozen=True)
class Answer:
    moves: list[str] = field(default_factory=list)
    number: int | None = None
    points: list[str] = field(default_factory=list)
    choice: str | None = None


@dataclass(frozen=True)
class Grade:
    correct: bool
    feedback_key: str
    done: bool = False  # the whole task is finished (all steps of a play task)
    reply: str | None = None  # scripted opponent move after a correct intermediate step
    marks: list[Mark] = field(default_factory=list)


def board_size(lesson: Lesson, setup: Setup) -> int:
    return setup.size or lesson.board_size


def initial_state(lesson: Lesson, setup: Setup) -> GameState:
    size = board_size(lesson, setup)
    board = Board.from_stones(
        size,
        [_pt(p, size) for p in setup.black],
        [_pt(p, size) for p in setup.white],
    )
    to_move = Color.BLACK if setup.to_move == "black" else Color.WHITE
    state = new_game(size, setup.komi, initial_board=board, to_move=to_move)
    for m in setup.moves:
        state = play(state, gtp_to_point(m, size))
    return state


def grade(lesson: Lesson, task: Task, answer: Answer) -> Grade:
    state = initial_state(lesson, task.setup)
    if task.kind == "play":
        return _grade_play(task, state, answer.moves)
    if task.kind == "count":
        assert task.count is not None
        return _grade_count(task.count, state, answer.number)
    if task.kind == "select":
        assert task.select is not None
        return _grade_select(task.select, state, answer.points)
    assert task.choose is not None
    return _grade_choose(task.choose, state, answer.choice)


# -- play ----------------------------------------------------------------------------------


def _grade_play(task: Task, state: GameState, moves: list[str]) -> Grade:
    size = state.size
    if not moves or len(moves) > len(task.steps):
        return Grade(False, FB + "bad_answer")
    for i, move in enumerate(moves):
        try:
            point = gtp_to_point(move, size)
        except ValueError:
            return Grade(False, FB + "bad_answer")
        legality = check_move(state, point)
        if legality is not Legality.OK:
            return Grade(False, FB + f"illegal.{legality.value}")
        before = state
        state = play(state, point)
        step = task.steps[i]
        ok, key = goal_met(step.goal, before, state, point)
        if not ok:
            return Grade(False, key)
        last = i == len(task.steps) - 1
        if last:
            return Grade(True, FB + "correct", done=True)
        reply = scripted_reply(step.reply, state) if step.reply else None
        if reply is not None:
            state = play(state, gtp_to_point(reply, size))
        if i == len(moves) - 1:
            return Grade(True, FB + "keep_going", done=False, reply=reply)
    raise AssertionError("unreachable")


def goal_met(
    goal: Goal, before: GameState, after: GameState, move: Point | None
) -> tuple[bool, str]:
    size = after.size
    board = after.board
    mover = before.to_move
    last = after.last_move
    captured = last.captured if last else frozenset()

    match goal:
        case PlaceAny():
            return move is not None, FB + "place_stone"
        case PlaceAt(points=points):
            return move is not None and point_to_gtp(move, size) in points, FB + "not_there"
        case Capture(min_stones=n, target=target):
            ok = len(captured) >= n and (target is None or _pt(target, size) in captured)
            return ok, FB + "not_capture"
        case Atari(target=target):
            if target is not None:
                g = board.group_at(_pt(target, size))
                return g is not None and len(g.liberties) == 1, FB + "not_atari"
            ok = any(len(g.liberties) == 1 for g in board.groups(mover.opponent))
            return ok, FB + "not_atari"
        case Escape(target=target, min_libs=n):
            g = board.group_at(_pt(target, size))
            return g is not None and len(g.liberties) >= n, FB + "not_escaped"
        case Connect(a=a, b=b):
            g = board.group_at(_pt(a, size))
            return g is not None and _pt(b, size) in g.stones, FB + "not_connected"
        case Cut(a=a, b=b):
            ga, gb = before.board.group_at(_pt(a, size)), before.board.group_at(_pt(b, size))
            ok = (
                move is not None
                and ga is not None
                and gb is not None
                and ga != gb
                and move in ga.liberties
                and move in gb.liberties
            )
            return ok, FB + "not_cut"
        case Pass():
            return move is None, FB + "not_pass"
        case TwoEyes(target=target):
            g = board.group_at(_pt(target, size))
            return g is not None and len(true_eyes(board, g)) >= 2, FB + "not_two_eyes"
    raise AssertionError(f"unknown goal {goal}")


def scripted_reply(reply: Reply, state: GameState) -> str:
    size = state.size
    if reply.type == "fixed":
        assert reply.move is not None
        return reply.move
    # save_atari: the side to move extends its largest chain that is in atari.
    in_atari = sorted(
        (g for g in state.board.groups(state.to_move) if len(g.liberties) == 1),
        key=lambda g: -g.size,
    )
    if reply.target is not None:
        in_atari = [g for g in in_atari if _pt(reply.target, size) in g.stones]
    for g in in_atari:
        lib = next(iter(g.liberties))
        if check_move(state, lib) is Legality.OK:
            return point_to_gtp(lib, size)
    return reply.fallback


# -- count / select / choose ---------------------------------------------------------------


def expected_count(spec: CountSpec, state: GameState) -> int:
    size = state.size
    if spec.type == "liberties":
        assert spec.target is not None
        g = state.board.group_at(_pt(spec.target, size))
        assert g is not None, f"no stone at {spec.target}"
        return len(g.liberties)
    score = area_score(state.board, state.komi, [_pt(p, size) for p in spec.dead])
    return score.black_area if spec.color == "black" else score.white_area


def _grade_count(spec: CountSpec, state: GameState, number: int | None) -> Grade:
    if number is None:
        return Grade(False, FB + "bad_answer")
    if number == expected_count(spec, state):
        return Grade(True, FB + "correct", done=True)
    marks: list[Mark] = []
    if spec.type == "liberties" and spec.target:
        g = state.board.group_at(_pt(spec.target, state.size))
        assert g is not None
        # Show the liberties so the learner can recount.
        marks = [
            Mark(point=point_to_gtp(p, state.size), kind="circle") for p in sorted(g.liberties)
        ]
    return Grade(False, FB + "wrong_count", marks=marks)


def expected_points(spec: SelectSpec, state: GameState) -> set[str]:
    size = state.size
    b = state.board
    match spec.type:
        case "liberties" | "false_eyes":
            assert spec.target is not None
            g = b.group_at(_pt(spec.target, size))
            assert g is not None, f"no stone at {spec.target}"
            pts = g.liberties if spec.type == "liberties" else false_eyes(b, g)
        case "suicide_points":
            pts = {p for p in b.points() if check_move(state, p) is Legality.SUICIDE}
        case "ko_point":
            pts = {p for p in b.points() if check_move(state, p) is Legality.KO}
        case "points":
            pts = {_pt(p, size) for p in spec.points}
    return {point_to_gtp(p, size) for p in pts}


def _grade_select(spec: SelectSpec, state: GameState, points: list[str]) -> Grade:
    try:
        chosen = {point_to_gtp(_pt(p, state.size), state.size) for p in points}
    except ValueError:
        return Grade(False, FB + "bad_answer")
    want = expected_points(spec, state)
    if not chosen:
        return Grade(False, FB + "bad_answer")
    if spec.mode == "one":
        ok = len(chosen) == 1 and chosen <= want
        return Grade(ok, FB + ("correct" if ok else "wrong_select"), done=ok)
    if chosen == want:
        return Grade(True, FB + "correct", done=True)
    return Grade(False, FB + ("incomplete" if chosen < want else "wrong_select"))


def expected_choice(spec: ChooseSpec, state: GameState) -> str:
    score = area_score(state.board, state.komi, [_pt(p, state.size) for p in spec.dead])
    w = score.winner
    return "draw" if w is None else ("black" if w is Color.BLACK else "white")


def _grade_choose(spec: ChooseSpec, state: GameState, choice: str | None) -> Grade:
    if choice is None:
        return Grade(False, FB + "bad_answer")
    ok = choice == expected_choice(spec, state)
    return Grade(ok, FB + ("correct" if ok else "wrong_choice"), done=ok)


def _pt(gtp: str, size: int) -> Point:
    p = gtp_to_point(gtp, size)
    if p is None:
        raise ValueError("pass is not a point")
    return p
