"""Belt exams: White -> Yellow (capture games, D-023) and Orange -> Brown (M8: 12 puzzles, then
best of 3 9x9 games without nudges)."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ishi.api.errors import ApiError
from ishi.api.routes_gym import LineFrame, NowDep, PuzzleOut, _board, _frames, _puzzle_out
from ishi.api.schemas import ErrorResponse
from ishi.bots.humansl_bot import rank_label
from ishi.db.models import Exam, Game, Puzzle, User
from ishi.db.session import SessionDep, get_or_create_user
from ishi.gym import service as gym
from ishi.gym.puzzles import Outcome
from ishi.play import service
from ishi.play.progression import (
    BELT_EXAM_LOSSES,
    BELT_EXAM_PUZZLES_TO_PASS,
    BELT_EXAM_WINS,
    EXAM_LOSSES_TO_FAIL,
    EXAM_WINS_TO_PASS,
    belt_exam_phase,
)
from ishi.why.selector import BELT_RANK

router = APIRouter(tags=["exams"])


class ExamPuzzleOut(BaseModel):
    puzzle: PuzzleOut
    solved: bool | None  # None = not answered yet


class ExamOut(BaseModel):
    id: str
    belt_target: str
    status: Literal["in_progress", "passed", "failed"]
    phase: Literal["puzzles", "games", "done"]  # Yellow exam: games only
    games_won: int
    games_lost: int
    wins_needed: int
    losses_allowed: int
    active_game: str | None  # unfinished exam game to resume
    puzzles: list[ExamPuzzleOut]  # Orange+: 12 puzzles first (Yellow exam has none, D-023)
    puzzles_needed: int  # solved puzzles needed to go on to the games
    puzzle_score: int  # solved so far
    bot_rank: float | None  # exam games' bot (Orange+: the belt's rank)
    bot_label: str | None
    created_at: datetime


class ExamAttemptIn(BaseModel):
    moves: list[str] = Field(min_length=1, max_length=21)  # learner, opponent, ..., learner
    time_ms: int | None = Field(default=None, ge=0)


class ExamAttemptOut(BaseModel):
    correct: bool
    done: bool  # the puzzle is answered (one try: a wrong move ends it)
    opponent_reply: str | None
    solution_line: list[str] | None  # once done
    solution_frames: list[LineFrame] | None
    board: LineFrame
    exam: ExamOut


def exam_or_404(session: Session, user: User, exam_id: str) -> Exam:
    exam = session.get(Exam, exam_id)
    if exam is None or exam.user_id != user.id:
        raise ApiError(404, "NOT_FOUND", "errors.not_found", {"exam_id": exam_id})
    return exam


def exam_phase(exam: Exam) -> str:
    if exam.belt_target == "yellow":
        return "games" if exam.status == "in_progress" else "done"
    return belt_exam_phase(service.puzzle_results(exam), exam.status)


def exam_bot_rank(exam: Exam) -> float | None:
    return BELT_RANK.get(exam.belt_target)


def exam_out(session: Session, exam: Exam) -> ExamOut:
    active = session.exec(
        select(Game).where(Game.exam_id == exam.id, Game.status == "active")
    ).first()
    yellow = exam.belt_target == "yellow"
    puzzles = []
    for item in exam.puzzles:
        pz = session.get(Puzzle, item["id"])
        if pz is not None:
            puzzles.append(ExamPuzzleOut(puzzle=_puzzle_out(pz), solved=item.get("solved")))
    rank = exam_bot_rank(exam)
    return ExamOut(
        id=exam.id,
        belt_target=exam.belt_target,
        status=exam.status,  # type: ignore[arg-type]
        phase=exam_phase(exam),  # type: ignore[arg-type]
        games_won=exam.games_won,
        games_lost=exam.games_lost,
        wins_needed=EXAM_WINS_TO_PASS if yellow else BELT_EXAM_WINS,
        losses_allowed=EXAM_LOSSES_TO_FAIL if yellow else BELT_EXAM_LOSSES,
        active_game=active.id if active and exam.status == "in_progress" else None,
        puzzles=puzzles,
        puzzles_needed=0 if yellow else BELT_EXAM_PUZZLES_TO_PASS,
        puzzle_score=sum(1 for s in service.puzzle_results(exam) if s),
        bot_rank=rank,
        bot_label=rank_label(rank) if rank is not None else None,
        created_at=exam.created_at,
    )


@router.post("/exams", response_model=ExamOut, responses={409: {"model": ErrorResponse}})
def create_exam(session: SessionDep) -> ExamOut:
    user = get_or_create_user(session)
    current = service.active_exam(session, user)
    if current is not None:
        return exam_out(session, current)
    if not service.can_take_exam(session, user):
        raise ApiError(409, "EXAM_NOT_AVAILABLE", "errors.exam_not_available", {})
    return exam_out(session, service.start_exam(session, user))


@router.get("/exams/{exam_id}", response_model=ExamOut, responses={404: {"model": ErrorResponse}})
def get_exam(session: SessionDep, exam_id: str) -> ExamOut:
    user = get_or_create_user(session)
    return exam_out(session, exam_or_404(session, user, exam_id))


@router.post(
    "/exams/{exam_id}/puzzles/{puzzle_id}/attempt",
    response_model=ExamAttemptOut,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def exam_attempt(
    session: SessionDep, now: NowDep, exam_id: str, puzzle_id: str, body: ExamAttemptIn
) -> ExamAttemptOut:
    """One try per puzzle and no hints: a wrong move answers it as not solved."""
    user = get_or_create_user(session)
    exam = exam_or_404(session, user, exam_id)
    index = next((i for i, p in enumerate(exam.puzzles) if p["id"] == puzzle_id), None)
    if index is None:
        raise ApiError(404, "PUZZLE_NOT_FOUND", "errors.puzzle_not_found", {"id": puzzle_id})
    if exam_phase(exam) != "puzzles" or exam.puzzles[index].get("solved") is not None:
        raise ApiError(409, "EXAM_PUZZLE_DONE", "errors.exam_puzzle_done", {"id": puzzle_id})
    pz = session.get(Puzzle, puzzle_id)
    assert pz is not None
    try:
        correct, done, reply = gym.grade(pz, body.moves)
    except gym.BadMoves as e:
        raise ApiError(422, "BAD_MOVES", "errors.invalid_request", {"reason": str(e)}) from None
    answered = done or not correct
    if answered:
        gym.finish(session, pz, Outcome(correct, 0, 0, body.time_ms), "exam", now)
        exam.puzzles = [
            {**p, "solved": correct} if i == index else p for i, p in enumerate(exam.puzzles)
        ]
        service.settle_exam(session, exam)
        session.commit()
        session.refresh(exam)
    return ExamAttemptOut(
        correct=correct,
        done=answered,
        opponent_reply=None if answered else reply,
        solution_line=list(pz.solution_line) if answered else None,
        solution_frames=_frames(pz) if answered else None,
        board=_board(pz, body.moves, None if answered else reply)
        if correct
        else _board(pz, body.moves[:-1], None),
        exam=exam_out(session, exam),
    )
