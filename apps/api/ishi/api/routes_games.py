"""Games against the bot: capture games (M2), full 9x9 vs HumanSL (M3), exam games."""

import random
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlmodel import Session

from ishi.api.errors import ApiError
from ishi.api.routes_exams import exam_bot_rank, exam_or_404, exam_phase
from ishi.api.schemas import ErrorResponse, GameStateOut, game_state_out, score_out
from ishi.bots.humansl_bot import PICKER_RANKS
from ishi.db.models import Game, User
from ishi.db.session import SessionDep, get_or_create_user
from ishi.engine.katago_process import EngineUnavailableError, KataGoProcess
from ishi.play import full_service, nudges, service
from ishi.play.progression import PLACEMENT
from ishi.progress import service as progress
from ishi.rules.coords import gtp_to_point
from ishi.rules.game import GameState, Legality, check_move
from ishi.rules.scoring import area_score
from ishi.rules.sgf import to_sgf

router = APIRouter(tags=["games"])

_rng = random.Random()


class NewGame(BaseModel):
    mode: Literal["capture", "full"] = "capture"
    exam_id: str | None = None
    bot_rank: float | None = Field(default=None, ge=-8, le=30)  # full; default adaptive


class MoveIn(BaseModel):
    point: str
    played_anyway: bool = False


class MoveOut(BaseModel):
    state: GameStateOut
    bot_move: str | None  # GTP, "pass", or "resign" (full games)
    game_over: bool


class PreviewIn(BaseModel):
    point: str
    locale: Literal["th", "en"] | None = None  # the screen's language (default: the learner's)


class NudgeOut(BaseModel):
    concept_id: str
    headline: str
    explanation: list[str]
    question: str  # the teacher's question; the answer is never in it
    hint_level_available: int  # hints 1 (question + marks) and 2 (highlighted area)
    nudges_left: int


class PreviewOut(BaseModel):
    legal: bool
    reason: str | None  # why it's illegal (errors.reason.*)
    nudge: NudgeOut | None


class GameHintIn(BaseModel):
    level: int = Field(ge=1, le=nudges.HINT_LEVELS)
    locale: Literal["th", "en"] | None = None


class GameHintOut(BaseModel):
    level: int
    text: str
    marks: list[str]  # the stones in question (triangles)
    focus: str | None  # level 2: center of the highlighted 3x3 area


class BotRanksOut(BaseModel):
    ranks: list[float]
    unlocked: bool  # full games open for this user (D-030)
    recommended: float  # the adaptive strength (M8): the picker's default


def _state_out(game: Game, state: GameState, user: User | None = None) -> GameStateOut:
    out = game_state_out(state, id=game.id, mode=game.mode, result=game.result)
    out.nudges_left = nudges.nudges_left(game, user) if user is not None else 0
    if game.status == "finished":
        out.status = "finished"
    out.exam_id = game.exam_id
    if game.mode == "capture":
        out.capture_target = service.target(game)
        out.bot_level = int(game.bot_params.get("level", 1))
        return out
    out.bot_rank = game.bot_rank
    out.bot_label = game.bot_params.get("label")
    fs = game.final_score
    if fs is not None:
        dead = [gtp_to_point(p, game.board_size) for p in fs["dead"]]
        out.score = score_out(area_score(state.board, game.komi, dead), state)
        out.dead = list(fs["dead"])
    return out


def _queue_analysis(request: Request, game: Game) -> None:
    """Background per-move analysis and, once the game is over, the Why Engine review (M4)."""
    worker = request.app.state.analysis
    if worker is not None and game.mode == "full":
        worker.enqueue(game.id)


def _game_or_404(session: Session, user: User, game_id: str) -> Game:
    game = session.get(Game, game_id)
    if game is None or game.user_id != user.id:
        raise ApiError(404, "NOT_FOUND", "errors.not_found", {"game_id": game_id})
    return game


@router.post("/games", response_model=GameStateOut, responses={409: {"model": ErrorResponse}})
async def create_game(request: Request, session: SessionDep, body: NewGame) -> GameStateOut:
    user = get_or_create_user(session)
    exam = None
    if body.exam_id is not None:
        exam = exam_or_404(session, user, body.exam_id)
        if exam.status != "in_progress":
            raise ApiError(409, "EXAM_FINISHED", "errors.exam_finished", {"exam_id": exam.id})
        if exam_phase(exam) != "games" or (exam.belt_target == "yellow") != (
            body.mode == "capture"
        ):
            raise ApiError(409, "EXAM_NOT_READY", "errors.exam_not_ready", {"exam_id": exam.id})
    if body.mode == "full":
        placement = exam is not None and exam.belt_target == PLACEMENT
        if not full_service.full_games_unlocked(user) and not placement:
            raise ApiError(409, "MODE_LOCKED", "errors.mode_locked", {"mode": "full"})
        if exam is not None:
            rank = exam_bot_rank(exam) or 25.0
        elif body.bot_rank is not None:
            rank = body.bot_rank
        else:
            rank = progress.default_bot_rank(user)
        game = full_service.start_full_game(session, user, rank, exam_id=exam.id if exam else None)
        state = service.load_state(session, game)
        _warm(request, game, user, state)
        return _state_out(game, state, user)
    game = service.start_game(session, user, exam)
    return _state_out(game, service.load_state(session, game))


@router.get("/games/bot-ranks", response_model=BotRanksOut)
def bot_ranks(session: SessionDep) -> BotRanksOut:
    """Strengths offered in the 9x9 picker (D-031); the adaptive one is the default (M8)."""
    user = get_or_create_user(session)
    return BotRanksOut(
        ranks=list(PICKER_RANKS),
        unlocked=full_service.full_games_unlocked(user),
        recommended=progress.default_bot_rank(user),
    )


@router.get(
    "/games/{game_id}", response_model=GameStateOut, responses={404: {"model": ErrorResponse}}
)
async def get_game(request: Request, session: SessionDep, game_id: str) -> GameStateOut:
    user = get_or_create_user(session)
    game = _game_or_404(session, user, game_id)
    state = service.load_state(session, game)
    _warm(request, game, user, state)
    return _state_out(game, state, user)


@router.post(
    "/games/{game_id}/moves",
    response_model=MoveOut,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def post_move(request: Request, session: SessionDep, game_id: str, body: MoveIn) -> MoveOut:
    user = get_or_create_user(session)
    game = _game_or_404(session, user, game_id)
    state = service.load_state(session, game)
    try:
        point = gtp_to_point(body.point, game.board_size)
    except ValueError:
        raise ApiError(
            422, "BAD_COORDINATE", "errors.bad_coordinate", {"point": body.point}
        ) from None
    legality = Legality.GAME_OVER if game.status == "finished" else check_move(state, point)
    if legality is not Legality.OK:
        raise ApiError(
            422,
            "ILLEGAL_MOVE",
            "errors.illegal_move",
            {"point": body.point, "reason": legality.value},
        )
    if game.mode == "full":
        engine: KataGoProcess | None = request.app.state.engine
        if engine is None:
            raise EngineUnavailableError("KataGo not configured")
        before = state
        state, bot_move = await full_service.play_full_move(
            session, game, state, point, engine, _rng
        )
        nudges.after_move(session, game, before, body.point.upper())
        _queue_analysis(request, game)
        _warm(request, game, user, state)
    else:  # the capture bot searches for up to ~1.5 s: keep it off the event loop
        state, bot_move = await run_in_threadpool(
            service.play_learner_move, session, game, state, point, _rng
        )
    session.refresh(game)
    return MoveOut(
        state=_state_out(game, state, user),
        bot_move=bot_move,
        game_over=game.status == "finished",
    )


def _locale(user: User) -> Literal["th", "en"]:
    return "en" if user.locale == "en" else "th"


def _warm(request: Request, game: Game, user: User, state: GameState) -> None:
    """Start analyzing the position the learner is thinking about (nudges, M7)."""
    if nudges.nudges_left(game, user) > 0 and not state.is_over:
        request.app.state.live.warm(game.id, state)


@router.post(
    "/games/{game_id}/preview",
    response_model=PreviewOut,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def preview(
    request: Request, session: SessionDep, game_id: str, body: PreviewIn
) -> PreviewOut:
    """Called on the ghost stone: is the move legal, and does the teacher want to ask first?"""
    user = get_or_create_user(session)
    game = _game_or_404(session, user, game_id)
    state = service.load_state(session, game)
    try:
        point = gtp_to_point(body.point, game.board_size)
    except ValueError:
        raise ApiError(
            422, "BAD_COORDINATE", "errors.bad_coordinate", {"point": body.point}
        ) from None
    legality = Legality.GAME_OVER if game.status == "finished" else check_move(state, point)
    if legality is not Legality.OK:
        return PreviewOut(legal=False, reason=legality.value, nudge=None)
    if point is None or not nudges.nudges_on(game, user):
        return PreviewOut(legal=True, reason=None, nudge=None)
    nudge = await nudges.preview(
        session,
        game,
        user,
        state,
        point,
        engine=request.app.state.engine,
        live=request.app.state.live,
    )
    if nudge is None:
        return PreviewOut(legal=True, reason=None, nudge=None)
    n = nudge.narration(body.locale or _locale(user))
    return PreviewOut(
        legal=True,
        reason=None,
        nudge=NudgeOut(
            concept_id=nudge.concept_id,
            headline=n.headline,
            explanation=n.explanation,
            question=n.question or "",
            hint_level_available=nudges.HINT_LEVELS,
            nudges_left=nudges.nudges_left(game, user),
        ),
    )


@router.post(
    "/games/{game_id}/hint",
    response_model=GameHintOut,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def game_hint(session: SessionDep, game_id: str, body: GameHintIn) -> GameHintOut:
    """Hints after a nudge: 1 = a guiding question and the stones in question, 2 = the area."""
    user = get_or_create_user(session)
    game = _game_or_404(session, user, game_id)
    nudge = nudges.pending(game, service.load_state(session, game))
    if nudge is None:
        raise ApiError(409, "NO_NUDGE", "errors.no_nudge", {"game_id": game_id})
    return GameHintOut(
        level=body.level,
        text=nudge.narration(body.locale or _locale(user)).hints[body.level - 1],
        marks=nudge.marks,
        focus=nudge.focus if body.level >= 2 else None,
    )


@router.post("/games/{game_id}/resign", response_model=GameStateOut)
def resign(request: Request, session: SessionDep, game_id: str) -> GameStateOut:
    user = get_or_create_user(session)
    game = _game_or_404(session, user, game_id)
    state = service.load_state(session, game)
    service.resign(session, game, state)
    session.refresh(game)
    _queue_analysis(request, game)
    return _state_out(game, state)


@router.get("/games/{game_id}/sgf", response_class=PlainTextResponse)
def game_sgf(session: SessionDep, game_id: str) -> str:
    user = get_or_create_user(session)
    game = _game_or_404(session, user, game_id)
    return game.sgf or to_sgf(service.load_state(session, game))
