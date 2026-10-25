"""Games against the bot (capture games M2, full 9x9 vs HumanSL M3) and the Yellow exam."""

import random
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ishi.api.errors import ApiError
from ishi.api.schemas import ErrorResponse, GameStateOut, game_state_out, score_out
from ishi.bots.humansl_bot import PICKER_RANKS
from ishi.db.models import Exam, Game, User
from ishi.db.session import SessionDep, get_or_create_user
from ishi.engine.katago_process import EngineUnavailableError, KataGoProcess
from ishi.play import full_service, service
from ishi.play.progression import EXAM_LOSSES_TO_FAIL, EXAM_WINS_TO_PASS
from ishi.rules.coords import gtp_to_point
from ishi.rules.game import GameState, Legality, check_move
from ishi.rules.scoring import area_score
from ishi.rules.sgf import to_sgf

router = APIRouter(tags=["games"])

_rng = random.Random()


class NewGame(BaseModel):
    mode: Literal["capture", "full"] = "capture"
    exam_id: str | None = None
    bot_rank: float | None = Field(default=None, ge=-8, le=30)  # full games; default weakest


class MoveIn(BaseModel):
    point: str
    played_anyway: bool = False


class MoveOut(BaseModel):
    state: GameStateOut
    bot_move: str | None  # GTP, "pass", or "resign" (full games)
    game_over: bool


class BotRanksOut(BaseModel):
    ranks: list[float]
    unlocked: bool  # full games open for this user (D-030)


class ExamOut(BaseModel):
    id: str
    belt_target: str
    status: Literal["in_progress", "passed", "failed"]
    games_won: int
    games_lost: int
    wins_needed: int
    losses_allowed: int
    active_game: str | None  # unfinished exam game to resume
    puzzles: list[str]  # Yellow exam has no puzzles (D-023)


def _state_out(game: Game, state: GameState) -> GameStateOut:
    out = game_state_out(state, id=game.id, mode=game.mode, result=game.result)
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


def _game_or_404(session: Session, user: User, game_id: str) -> Game:
    game = session.get(Game, game_id)
    if game is None or game.user_id != user.id:
        raise ApiError(404, "NOT_FOUND", "errors.not_found", {"game_id": game_id})
    return game


def _exam_or_404(session: Session, user: User, exam_id: str) -> Exam:
    exam = session.get(Exam, exam_id)
    if exam is None or exam.user_id != user.id:
        raise ApiError(404, "NOT_FOUND", "errors.not_found", {"exam_id": exam_id})
    return exam


@router.post("/games", response_model=GameStateOut, responses={409: {"model": ErrorResponse}})
def create_game(session: SessionDep, body: NewGame) -> GameStateOut:
    user = get_or_create_user(session)
    if body.mode == "full":
        if not full_service.full_games_unlocked(user):
            raise ApiError(409, "MODE_LOCKED", "errors.mode_locked", {"mode": "full"})
        rank = body.bot_rank if body.bot_rank is not None else max(PICKER_RANKS)
        game = full_service.start_full_game(session, user, rank)
        return _state_out(game, service.load_state(session, game))
    exam = None
    if body.exam_id is not None:
        exam = _exam_or_404(session, user, body.exam_id)
        if exam.status != "in_progress":
            raise ApiError(409, "EXAM_FINISHED", "errors.exam_finished", {"exam_id": exam.id})
    game = service.start_game(session, user, exam)
    return _state_out(game, service.load_state(session, game))


@router.get("/games/bot-ranks", response_model=BotRanksOut)
def bot_ranks(session: SessionDep) -> BotRanksOut:
    """Strengths offered in the 9x9 picker until adaptive strength (M8), D-031."""
    user = get_or_create_user(session)
    return BotRanksOut(ranks=list(PICKER_RANKS), unlocked=full_service.full_games_unlocked(user))


@router.get(
    "/games/{game_id}", response_model=GameStateOut, responses={404: {"model": ErrorResponse}}
)
def get_game(session: SessionDep, game_id: str) -> GameStateOut:
    user = get_or_create_user(session)
    game = _game_or_404(session, user, game_id)
    return _state_out(game, service.load_state(session, game))


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
        state, bot_move = await full_service.play_full_move(
            session, game, state, point, engine, _rng
        )
    else:  # the capture bot searches for up to ~1.5 s: keep it off the event loop
        state, bot_move = await run_in_threadpool(
            service.play_learner_move, session, game, state, point, _rng
        )
    session.refresh(game)
    return MoveOut(
        state=_state_out(game, state), bot_move=bot_move, game_over=game.status == "finished"
    )


@router.post("/games/{game_id}/resign", response_model=GameStateOut)
def resign(session: SessionDep, game_id: str) -> GameStateOut:
    user = get_or_create_user(session)
    game = _game_or_404(session, user, game_id)
    state = service.load_state(session, game)
    service.resign(session, game, state)
    session.refresh(game)
    return _state_out(game, state)


@router.get("/games/{game_id}/sgf", response_class=PlainTextResponse)
def game_sgf(session: SessionDep, game_id: str) -> str:
    user = get_or_create_user(session)
    game = _game_or_404(session, user, game_id)
    return game.sgf or to_sgf(service.load_state(session, game))


# -- exams -------------------------------------------------------------------------------


def _exam_out(session: Session, exam: Exam) -> ExamOut:
    active = session.exec(
        select(Game).where(Game.exam_id == exam.id, Game.status == "active")
    ).first()
    return ExamOut(
        id=exam.id,
        belt_target=exam.belt_target,
        status=exam.status,  # type: ignore[arg-type]
        games_won=exam.games_won,
        games_lost=exam.games_lost,
        wins_needed=EXAM_WINS_TO_PASS,
        losses_allowed=EXAM_LOSSES_TO_FAIL,
        active_game=active.id if active and exam.status == "in_progress" else None,
        puzzles=[],
    )


@router.post("/exams", response_model=ExamOut, responses={409: {"model": ErrorResponse}})
def create_exam(session: SessionDep) -> ExamOut:
    user = get_or_create_user(session)
    current = service.active_exam(session, user)
    if current is not None:
        return _exam_out(session, current)
    if not service.can_take_exam(session, user):
        raise ApiError(409, "EXAM_NOT_AVAILABLE", "errors.exam_not_available", {})
    return _exam_out(session, service.start_exam(session, user))


@router.get("/exams/{exam_id}", response_model=ExamOut, responses={404: {"model": ErrorResponse}})
def get_exam(session: SessionDep, exam_id: str) -> ExamOut:
    user = get_or_create_user(session)
    return _exam_out(session, _exam_or_404(session, user, exam_id))
