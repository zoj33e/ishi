"""Post-game lessons (M5, 08-api-spec): the lesson of a game, its retry, hints and completion."""

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from ishi.api.errors import ApiError
from ishi.api.schemas import ErrorResponse, GameStateOut, Stones, game_state_out
from ishi.config import get_settings
from ishi.db.models import Game, Lesson, User
from ishi.db.session import SessionDep, get_or_create_user
from ishi.play import lessons
from ishi.play.review_service import learner_color
from ishi.rules.coords import gtp_to_point
from ishi.rules.game import Legality, check_move
from ishi.teacher.narration import Narration

router = APIRouter(tags=["lessons"])

Locale = Literal["th", "en"]


class GameLessonPreparing(BaseModel):
    # preparing: analysis or narration still running; unavailable: no engine to analyze with
    status: Literal["preparing", "unavailable"]


class LineFrame(BaseModel):
    stones: Stones
    last_move: str | None


class GameLessonOut(BaseModel):
    lesson_id: str
    game_id: str
    lesson_type: Literal["mistake", "praise", "clean"]
    concept_id: str | None
    variant: str | None
    move_number: int | None
    learner_color: Literal["black", "white"]
    position: GameStateOut  # before the learner's move (whole game for a clean lesson)
    played_move: str | None
    severity: Literal["small", "medium", "big"] | None  # mistake size (never raw points)
    threat_move: str | None  # praise: the opponent's threat the learner answered
    follow_up_line: list[str]  # "W E5", ...: what the opponent does after the learner's move
    narration: Narration
    can_retry: bool
    attempts: int
    hint_level: int  # 0 none, 1 guiding question, 2 highlighted area, 3 solution shown
    retry_result: Literal["solved_first", "solved_hint", "failed"] | None
    focus: str | None  # center of the highlighted 3x3 area (from hint level 2)
    solution_line: list[str]  # "B E5", ...: shown once solved or revealed
    solution_frames: list[LineFrame]  # the board after each ply of solution_line
    done: bool


class RetryIn(BaseModel):
    point: str


class RetryOut(BaseModel):
    correct: bool
    feedback_key: str  # i18n key: lesson.retry.correct / tryAgain / solution
    lesson: GameLessonOut


class DoneOut(BaseModel):
    puzzle_added: bool


def _lesson_out(session: Session, game: Game, lesson: Lesson) -> GameLessonOut:
    pkg = lessons.package(lesson)
    state = lessons.lesson_position(session, game, lesson)
    color = learner_color(game)
    position = game_state_out(state, id=game.id, mode=game.mode, learner_color=color)
    revealed = lesson.retry_result is not None or lesson.hint_level >= lessons.HINT_SOLUTION
    line = lesson.solution_line if revealed else []
    frames = []
    for f in lessons.line_frames(state, line):
        out = game_state_out(f, id=game.id, mode=game.mode)
        frames.append(LineFrame(stones=out.stones, last_move=out.last_move))
    return GameLessonOut(
        lesson_id=lesson.id,
        game_id=game.id,
        lesson_type=pkg.lesson_type,  # type: ignore[arg-type]
        concept_id=pkg.concept_id,
        variant=pkg.variant,
        move_number=lesson.move_number,
        learner_color=pkg.learner_color,
        position=position,
        played_move=pkg.played_move,
        severity=lessons.severity(pkg.points_lost) if pkg.lesson_type == "mistake" else None,
        threat_move=pkg.threat_move,
        follow_up_line=pkg.follow_up_line,
        narration=Narration.model_validate(lesson.narration),
        can_retry=lessons.can_retry(lesson),
        attempts=lesson.attempts,
        hint_level=lesson.hint_level,
        retry_result=lesson.retry_result,  # type: ignore[arg-type]
        focus=lessons.focus_point(lesson) if lesson.hint_level >= lessons.HINT_AREA else None,
        solution_line=line,
        solution_frames=frames,
        done=lesson.done_at is not None,
    )


def _game_or_404(session: Session, user: User, game_id: str) -> Game:
    game = session.get(Game, game_id)
    if game is None or game.user_id != user.id:
        raise ApiError(404, "NOT_FOUND", "errors.not_found", {"game_id": game_id})
    return game


def _lesson_or_404(session: Session, user: User, lesson_id: str) -> tuple[Lesson, Game]:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None or lesson.user_id != user.id:
        raise ApiError(404, "NOT_FOUND", "errors.not_found", {"lesson_id": lesson_id})
    game = session.get(Game, lesson.game_id)
    assert game is not None
    return lesson, game


@router.get(
    "/games/{game_id}/lesson",
    response_model=GameLessonOut,
    responses={
        202: {"model": GameLessonPreparing},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def get_lesson(
    request: Request, session: SessionDep, game_id: str, locale: Locale | None = None
) -> GameLessonOut | JSONResponse:
    user = get_or_create_user(session)
    game = _game_or_404(session, user, game_id)
    if game.mode != "full":
        raise ApiError(404, "NOT_FOUND", "errors.not_found", {"game_id": game_id})
    if game.status != "finished":
        raise ApiError(409, "GAME_NOT_FINISHED", "errors.game_not_finished", {"game_id": game_id})
    teacher = request.app.state.teacher
    model = get_settings().llm_model
    lesson = session.exec(select(Lesson).where(Lesson.game_id == game.id)).first()
    if lesson is None:
        if game.reviewed_at is None:
            worker = request.app.state.analysis
            if worker is None:
                return JSONResponse(GameLessonPreparing(status="unavailable").model_dump(), 202)
            worker.enqueue(game.id)
            return JSONResponse(GameLessonPreparing(status="preparing").model_dump(), 202)
        lesson = await lessons.build_lesson(
            session, game, teacher, model, lessons.RELOCALIZE_BUDGET
        )
    lesson = await lessons.relocalize(session, lesson, locale or user_locale(user), teacher, model)
    lessons.mark_viewed(session, lesson)
    return _lesson_out(session, game, lesson)


def user_locale(user: User) -> Locale:
    return "en" if user.locale == "en" else "th"


@router.post(
    "/lessons/{lesson_id}/retry",
    response_model=RetryOut,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def retry(session: SessionDep, lesson_id: str, body: RetryIn) -> RetryOut:
    user = get_or_create_user(session)
    lesson, game = _lesson_or_404(session, user, lesson_id)
    if not lessons.can_retry(lesson):
        raise ApiError(409, "RETRY_CLOSED", "errors.retry_closed", {"lesson_id": lesson_id})
    state = lessons.lesson_position(session, game, lesson)
    try:
        point = gtp_to_point(body.point, game.board_size)
    except ValueError:
        raise ApiError(
            422, "BAD_COORDINATE", "errors.bad_coordinate", {"point": body.point}
        ) from None
    legality = check_move(state, point)
    if legality is not Legality.OK:
        details = {"point": body.point, "reason": legality.value}
        raise ApiError(422, "ILLEGAL_MOVE", "errors.illegal_move", details)
    correct = lessons.retry(session, lesson, body.point)
    if correct:
        key = "lesson.retry.correct"
    elif lesson.retry_result == "failed":
        key = "lesson.retry.solution"
    else:
        key = "lesson.retry.tryAgain"
    return RetryOut(correct=correct, feedback_key=key, lesson=_lesson_out(session, game, lesson))


@router.post(
    "/lessons/{lesson_id}/hint",
    response_model=GameLessonOut,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def hint(session: SessionDep, lesson_id: str) -> GameLessonOut:
    """One step up the hint ladder: guiding question, highlighted area, then the solution."""
    user = get_or_create_user(session)
    lesson, game = _lesson_or_404(session, user, lesson_id)
    if not lessons.can_retry(lesson):
        raise ApiError(409, "RETRY_CLOSED", "errors.retry_closed", {"lesson_id": lesson_id})
    lessons.next_hint(session, lesson)
    return _lesson_out(session, game, lesson)


@router.post(
    "/lessons/{lesson_id}/done", response_model=DoneOut, responses={404: {"model": ErrorResponse}}
)
def done(session: SessionDep, lesson_id: str) -> DoneOut:
    user = get_or_create_user(session)
    lesson, game = _lesson_or_404(session, user, lesson_id)
    return DoneOut(puzzle_added=lessons.finish_lesson(session, game, lesson))
