"""Rules school (M2): lesson list, localized lesson content, and engine-graded answers (D-026)."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ishi.api.errors import ApiError
from ishi.api.schemas import Captures, ColorName, ErrorResponse, Stones, color_name
from ishi.db.models import LessonProgress, User, utcnow
from ishi.db.session import SessionDep, get_or_create_user
from ishi.rules.board import Color
from ishi.rules.coords import gtp_to_point, point_to_gtp
from ishi.rules.game import GameState, play
from ishi.school.content import Lesson, Mark, Setup, Task, get_lesson, load_lessons
from ishi.school.grading import Answer, grade, initial_state

router = APIRouter(prefix="/school", tags=["school"])

Locale = Literal["th", "en"]
LessonStatus = Literal["locked", "available", "done"]


class Position(BaseModel):
    board_size: int
    komi: float
    to_move: ColorName
    stones: Stones
    last_move: str | None
    ko_point: str | None
    captures: Captures


def position(state: GameState) -> Position:
    size = state.size
    last = state.last_move
    return Position(
        board_size=size,
        komi=state.komi,
        to_move=color_name(state.to_move),
        stones=Stones(
            black=[point_to_gtp(p, size) for p in state.board.stones(Color.BLACK)],
            white=[point_to_gtp(p, size) for p in state.board.stones(Color.WHITE)],
        ),
        last_move=point_to_gtp(last.point, size) if last else None,
        ko_point=point_to_gtp(state.ko_point, size) if state.ko_point else None,
        captures=Captures(black=state.captures_black, white=state.captures_white),
    )


class LessonSummary(BaseModel):
    id: str
    order: int
    title: str
    status: LessonStatus
    tasks_total: int
    tasks_done: int


class SchoolOut(BaseModel):
    lessons: list[LessonSummary]
    next_lesson: str | None  # first lesson not done yet


class DemoFrameOut(BaseModel):
    text: str
    move: str | None
    marks: list[Mark]
    position: Position  # board after this frame's move


class TaskOut(BaseModel):
    id: str
    kind: Literal["play", "count", "select", "choose"]
    prompt: str
    hint: str
    success: str
    position: Position
    steps: int  # play: number of learner moves
    select_mode: Literal["one", "all"] | None
    done: bool


class LessonOut(BaseModel):
    id: str
    order: int
    board_size: int
    title: str
    idea: str
    takeaway: str
    status: LessonStatus
    demo: list[DemoFrameOut]
    tasks: list[TaskOut]


class AnswerIn(BaseModel):
    moves: list[str] = Field(default_factory=list, max_length=20)
    number: int | None = None
    points: list[str] = Field(default_factory=list, max_length=400)
    choice: Literal["black", "white", "draw"] | None = None


class AnswerOut(BaseModel):
    correct: bool
    feedback_key: str
    marks: list[Mark]
    done: bool  # this task is finished
    reply: str | None  # scripted opponent move after a correct intermediate step
    position: Position | None  # play tasks: board after the learner's moves (and reply)
    lesson_done: bool


# -- progress ----------------------------------------------------------------------------


def _progress(session: Session, user: User) -> dict[str, LessonProgress]:
    rows = session.exec(select(LessonProgress).where(LessonProgress.user_id == user.id))
    return {r.lesson_id: r for r in rows}


def _statuses(progress: dict[str, LessonProgress]) -> dict[str, LessonStatus]:
    """Sequential unlock: a lesson opens once every earlier lesson is done."""
    out: dict[str, LessonStatus] = {}
    open_ = True
    for lesson in load_lessons():
        done = lesson.id in progress and progress[lesson.id].status == "done"
        out[lesson.id] = "done" if done else ("available" if open_ else "locked")
        open_ = open_ and done
    return out


def next_lesson(session: Session, user: User) -> str | None:
    statuses = _statuses(_progress(session, user))
    return next((lid for lid, s in statuses.items() if s == "available"), None)


def _lesson_or_404(lesson_id: str) -> Lesson:
    lesson = get_lesson(lesson_id)
    if lesson is None:
        raise ApiError(404, "NOT_FOUND", "errors.not_found", {"lesson_id": lesson_id})
    return lesson


def _setup_position(lesson: Lesson, setup: Setup) -> Position:
    return position(initial_state(lesson, setup))


# -- routes ------------------------------------------------------------------------------


@router.get("", response_model=SchoolOut)
def school(session: SessionDep, locale: Locale | None = None) -> SchoolOut:
    user = get_or_create_user(session)
    loc = locale or user.locale
    progress = _progress(session, user)
    statuses = _statuses(progress)
    lessons = [
        LessonSummary(
            id=lesson.id,
            order=lesson.order,
            title=lesson.title.get(loc),
            status=statuses[lesson.id],
            tasks_total=len(lesson.tasks),
            tasks_done=len(set(progress[lesson.id].tasks_done)) if lesson.id in progress else 0,
        )
        for lesson in load_lessons()
    ]
    nxt = next((s.id for s in lessons if s.status == "available"), None)
    return SchoolOut(lessons=lessons, next_lesson=nxt)


@router.get("/{lesson_id}", response_model=LessonOut, responses={404: {"model": ErrorResponse}})
def lesson_detail(session: SessionDep, lesson_id: str, locale: Locale | None = None) -> LessonOut:
    lesson = _lesson_or_404(lesson_id)
    user = get_or_create_user(session)
    loc = locale or user.locale
    progress = _progress(session, user)
    done_tasks = set(progress[lesson.id].tasks_done) if lesson.id in progress else set()

    frames: list[DemoFrameOut] = []
    state = initial_state(lesson, lesson.demo.setup)
    for f in lesson.demo.frames:
        if f.move:
            state = play(state, gtp_to_point(f.move, state.size))
        frames.append(
            DemoFrameOut(text=f.text.get(loc), move=f.move, marks=f.marks, position=position(state))
        )

    def task_out(t: Task) -> TaskOut:
        return TaskOut(
            id=t.id,
            kind=t.kind,
            prompt=t.prompt.get(loc),
            hint=t.hint.get(loc),
            success=t.success.get(loc),
            position=_setup_position(lesson, t.setup),
            steps=len(t.steps),
            select_mode=t.select.mode if t.select else None,
            done=t.id in done_tasks,
        )

    return LessonOut(
        id=lesson.id,
        order=lesson.order,
        board_size=lesson.board_size,
        title=lesson.title.get(loc),
        idea=lesson.idea.get(loc),
        takeaway=lesson.takeaway.get(loc),
        status=_statuses(progress)[lesson.id],
        demo=frames,
        tasks=[task_out(t) for t in lesson.tasks],
    )


@router.post(
    "/{lesson_id}/tasks/{task_id}/answer",
    response_model=AnswerOut,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def answer(session: SessionDep, lesson_id: str, task_id: str, body: AnswerIn) -> AnswerOut:
    lesson = _lesson_or_404(lesson_id)
    task = lesson.task(task_id)
    if task is None:
        raise ApiError(404, "NOT_FOUND", "errors.not_found", {"task_id": task_id})
    user = get_or_create_user(session)
    progress = _progress(session, user)
    if _statuses(progress)[lesson.id] == "locked":
        raise ApiError(409, "LESSON_LOCKED", "errors.lesson_locked", {"lesson_id": lesson_id})

    g = grade(
        lesson,
        task,
        Answer(moves=body.moves, number=body.number, points=body.points, choice=body.choice),
    )

    pos: Position | None = None
    if task.kind == "play" and g.correct:
        state = initial_state(lesson, task.setup)
        for m in body.moves:
            state = play(state, gtp_to_point(m, state.size))
        if g.reply:
            state = play(state, gtp_to_point(g.reply, state.size))
        pos = position(state)

    row = progress.get(lesson.id) or LessonProgress(user_id=user.id, lesson_id=lesson.id)
    row.attempts += 1
    if g.done and task.id not in row.tasks_done:
        row.tasks_done = [*row.tasks_done, task.id]
    if all(t.id in row.tasks_done for t in lesson.tasks):
        row.status = "done"
    elif row.status != "done":
        row.status = "available"
    row.updated_at = utcnow()
    session.add(row)
    session.commit()

    return AnswerOut(
        correct=g.correct,
        feedback_key=g.feedback_key,
        marks=g.marks,
        done=g.done,
        reply=g.reply,
        position=pos,
        lesson_done=row.status == "done",
    )
