"""Shape Gym (M6, 08-api-spec): today's puzzles, attempts and hints."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from ishi.api.errors import ApiError
from ishi.api.routes_lessons import LineFrame
from ishi.api.schemas import ColorName, ErrorResponse, GameStateOut, color_name, game_state_out
from ishi.db.models import Puzzle, User
from ishi.db.session import SessionDep, get_or_create_user
from ishi.gym import service as gym
from ishi.play import lessons
from ishi.rules.coords import point_to_gtp

router = APIRouter(prefix="/gym", tags=["gym"])

Context = Literal["warmup", "gym", "exam"]
RatingName = Literal["again", "hard", "good", "easy"]


def get_now() -> datetime:
    """The clock (tests freeze it with a dependency override)."""
    return gym.local_now()


NowDep = Annotated[datetime, Depends(get_now)]


class PuzzleOut(BaseModel):
    id: str
    concept_id: str
    source: Literal["own_mistake", "seed"]
    to_move: ColorName
    learner_moves: int  # moves the learner plays (the opponent answers in between)
    position: GameStateOut


class DueOut(BaseModel):
    puzzles: list[PuzzleOut]
    due_today: int  # cards due today, before any top-up


class AttemptIn(BaseModel):
    moves: list[str] = Field(min_length=1, max_length=21)  # learner, opponent, ..., learner
    hints_used: int = Field(default=0, ge=0, le=3)
    time_ms: int | None = Field(default=None, ge=0)
    wrong_tries: int = Field(default=0, ge=0)  # wrong moves before this one
    context: Context = "gym"


class AttemptOut(BaseModel):
    correct: bool
    done: bool
    solved: bool
    opponent_reply: str | None  # play it, then send the next learner move
    solution_line: list[str] | None  # "B E5", ...: once done
    solution_frames: list[LineFrame] | None
    rating: RatingName | None
    next_due_at: datetime | None
    board: LineFrame  # the board now: after a correct move (and the reply), else unchanged


class HintIn(BaseModel):
    level: int = Field(ge=1, le=3)
    hints_used: int = Field(default=0, ge=0, le=3)
    time_ms: int | None = Field(default=None, ge=0)
    wrong_tries: int = Field(default=0, ge=0)
    context: Context = "gym"


class HintOut(BaseModel):
    level: int
    concept_id: str  # level 1: the client shows `gym.hint.<concept>`
    marks: list[str]  # level 1: stones of the group the puzzle is about
    focus: str | None  # level 2: center of the highlighted 3x3 area
    solution_line: list[str] | None  # level 3: the answer (the puzzle counts as failed)
    solution_frames: list[LineFrame] | None
    rating: RatingName | None
    next_due_at: datetime | None


def _puzzle_out(p: Puzzle) -> PuzzleOut:
    state = gym.puzzle_state(p)
    return PuzzleOut(
        id=p.id,
        concept_id=p.concept_id,
        source="seed" if p.source == "seed" else "own_mistake",
        to_move=color_name(state.to_move),
        learner_moves=p.learner_moves,
        position=game_state_out(state, id=p.id, mode="puzzle", learner_color=state.to_move),
    )


def _frames(p: Puzzle) -> list[LineFrame]:
    out = []
    for f in lessons.line_frames(gym.puzzle_state(p), list(p.solution_line)):
        s = game_state_out(f, id=p.id, mode="puzzle")
        out.append(LineFrame(stones=s.stones, last_move=s.last_move))
    return out


def _board(p: Puzzle, moves: list[str], reply: str | None) -> LineFrame:
    state = gym.replay(p, [*moves, reply] if reply else moves)
    s = game_state_out(state, id=p.id, mode="puzzle")
    return LineFrame(stones=s.stones, last_move=s.last_move)


def _puzzle(session: Session, user: User, puzzle_id: str) -> Puzzle:
    p = session.get(Puzzle, puzzle_id)
    if p is None or p.user_id != user.id:
        raise ApiError(404, "PUZZLE_NOT_FOUND", "errors.puzzle_not_found", {"id": puzzle_id})
    return p


@router.get("/due", response_model=DueOut)
def due(
    session: SessionDep,
    now: NowDep,
    limit: Annotated[int, Query(ge=1, le=gym.MAX_DUE)] = gym.MAX_DUE,
    context: Context = "gym",
) -> DueOut:
    user = get_or_create_user(session)
    due_today = gym.due_count(session, user.id, now)
    puzzles = gym.queue(session, user, now, context, limit)
    return DueOut(puzzles=[_puzzle_out(p) for p in puzzles], due_today=due_today)


@router.post(
    "/puzzles/{puzzle_id}/attempt",
    response_model=AttemptOut,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def attempt(puzzle_id: str, body: AttemptIn, session: SessionDep, now: NowDep) -> AttemptOut:
    user = get_or_create_user(session)
    p = _puzzle(session, user, puzzle_id)
    try:
        g = gym.attempt(
            session,
            p,
            body.moves,
            hints_used=body.hints_used,
            time_ms=body.time_ms,
            wrong_tries=body.wrong_tries,
            context=body.context,
            now=now,
        )
    except gym.BadMoves as e:
        raise ApiError(422, "BAD_MOVES", "errors.invalid_request", {"reason": str(e)}) from e
    return AttemptOut(
        correct=g.correct,
        done=g.done,
        solved=g.solved,
        opponent_reply=g.opponent_reply,
        solution_line=g.solution_line,
        solution_frames=_frames(p) if g.done else None,
        rating=g.rating,
        next_due_at=g.next_due_at,
        board=_board(p, body.moves if g.correct else body.moves[:-1], g.opponent_reply),
    )


@router.post(
    "/puzzles/{puzzle_id}/hint", response_model=HintOut, responses={404: {"model": ErrorResponse}}
)
def hint(puzzle_id: str, body: HintIn, session: SessionDep, now: NowDep) -> HintOut:
    user = get_or_create_user(session)
    p = _puzzle(session, user, puzzle_id)
    group = gym.target_group(p)
    marks = sorted(point_to_gtp(s, p.board_size) for s in group.stones) if group is not None else []
    out = HintOut(
        level=body.level,
        concept_id=p.concept_id,
        marks=marks,
        focus=None,
        solution_line=None,
        solution_frames=None,
        rating=None,
        next_due_at=None,
    )
    if body.level >= 2:
        out.focus = p.correct_moves[0] if p.correct_moves else None
    if body.level == 3:
        result, due_at = gym.give_up(
            session,
            p,
            hints_used=max(body.hints_used, 3),
            time_ms=body.time_ms,
            wrong_tries=body.wrong_tries,
            context=body.context,
            now=now,
        )
        out.solution_line = list(p.solution_line)
        out.solution_frames = _frames(p)
        out.rating = result
        out.next_due_at = due_at
    return out
