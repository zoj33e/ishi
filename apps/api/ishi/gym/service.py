"""Shape Gym (M6): the due queue, grading attempts, hints and scheduling.

Cards: an own-mistake puzzle gets a card when its lesson is done (first due the next day); a seed
puzzle gets one when it is first served. The warm-up shows the cards due today (at most 8); with
fewer than 3 it is topped up with new seed puzzles of the learner's weakest concept (D-052).

Multi-move puzzles are capture chases: the defender always extends at its last liberty, and each
later learner move must keep the chase going (captured, or atari with a working ladder) - judged by
the rules, so the gym never waits for KataGo (D-053).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal

from sqlmodel import Session, col, func, select

from ishi.db.models import Mistake, Puzzle, PuzzleAttempt, SrsCard, User
from ishi.gym import fsrs_service
from ishi.gym.puzzles import (
    FAILED_TRIES,
    Outcome,
    Rating,
    chase_holds,
    defender_reply,
    load_seed,
    rating,
)
from ishi.rules.board import Board, Color, Group
from ishi.rules.coords import Point, gtp_to_point, point_to_gtp
from ishi.rules.game import GameState, Legality, check_move, new_game, play
from ishi.why.selector import CONCEPT_BELT, concept_unlocked

Context = Literal["warmup", "gym", "exam"]
MAX_DUE = 8
MIN_WARMUP = 3
FIRST_DUE = timedelta(days=1)  # an own-mistake puzzle comes back the next day
ALWAYS_OPEN = "yellow"  # concepts from this belt are practised even at White belt
CONCEPT_ORDER = list(CONCEPT_BELT)


def local_now() -> datetime:
    """The server's local time (the app runs on the learner's PC); tests override it."""
    return datetime.now().astimezone()


class BadMoves(ValueError):
    """The submitted move sequence can't be replayed on the puzzle."""


# -- positions ------------------------------------------------------------------------------


def _pt(gtp: str, size: int) -> Point:
    p = gtp_to_point(gtp, size)
    if p is None:
        raise BadMoves(f"not a board point: {gtp}")
    return p


def puzzle_state(puzzle: Puzzle) -> GameState:
    s = puzzle.setup
    size = puzzle.board_size
    board = Board.from_stones(
        size, [_pt(g, size) for g in s["black"]], [_pt(g, size) for g in s["white"]]
    )
    state = new_game(
        size, s.get("komi", 7.0), initial_board=board, to_move=Color.parse(s["to_move"])
    )
    ko = s.get("ko_point")
    return replace(state, ko_point=_pt(ko, size)) if ko else state


def replay(puzzle: Puzzle, moves: list[str]) -> GameState:
    """The puzzle after `moves` (all legal - already checked by `grade`)."""
    state = puzzle_state(puzzle)
    for gtp in moves:
        state = play(state, _pt(gtp, puzzle.board_size))
    return state


def target_group(puzzle: Puzzle) -> Group | None:
    target = puzzle.setup.get("target")
    if not target:
        return None
    return puzzle_state(puzzle).board.group_at(_pt(target, puzzle.board_size))


# -- the queue ------------------------------------------------------------------------------


def due_count(session: Session, user_id: str, now: datetime) -> int:
    q = select(func.count()).where(
        SrsCard.user_id == user_id, SrsCard.due_at < fsrs_service.day_end(now)
    )
    return min(session.exec(q).one(), MAX_DUE)


def _due(session: Session, user_id: str, now: datetime, limit: int) -> list[Puzzle]:
    q = (
        select(Puzzle)
        .join(SrsCard, col(SrsCard.puzzle_id) == col(Puzzle.id))
        .where(SrsCard.user_id == user_id, SrsCard.due_at < fsrs_service.day_end(now))
        .order_by(col(SrsCard.due_at), col(Puzzle.created_at))
        .limit(limit)
    )
    return list(session.exec(q).all())


def open_concepts(belt: str) -> list[str]:
    return [c for c in CONCEPT_ORDER if CONCEPT_BELT[c] == ALWAYS_OPEN or concept_unlocked(c, belt)]


def weakest_concepts(session: Session, user: User) -> list[str]:
    """Open concepts, weakest first: most eligible game mistakes, then lowest puzzle success."""
    mistakes = dict(
        session.exec(
            select(Mistake.concept_id, func.count())
            .where(Mistake.user_id == user.id, col(Mistake.eligible))
            .group_by(col(Mistake.concept_id))
        ).all()
    )
    tries: dict[str, list[int]] = {}
    rows = session.exec(
        select(Puzzle.concept_id, PuzzleAttempt.result)
        .join(Puzzle, col(Puzzle.id) == col(PuzzleAttempt.puzzle_id))
        .where(PuzzleAttempt.user_id == user.id)
    ).all()
    for concept, result in rows:
        tries.setdefault(concept, []).append(0 if result == "again" else 1)

    def success(c: str) -> float:
        t = tries.get(c)
        return sum(t) / len(t) if t else 0.5

    concepts = open_concepts(user.belt)
    return sorted(concepts, key=lambda c: (-mistakes.get(c, 0), success(c), CONCEPT_ORDER.index(c)))


def serve_seeds(session: Session, user: User, now: datetime, n: int) -> list[Puzzle]:
    """`n` new seed puzzles (weakest concept first), each with a card due now."""
    if n <= 0:
        return []
    seen = set(
        session.exec(
            select(Puzzle.seed_id).where(Puzzle.user_id == user.id, col(Puzzle.seed_id).isnot(None))
        ).all()
    )
    out: list[Puzzle] = []
    seeds = load_seed()
    for concept in weakest_concepts(session, user):
        for item in seeds:
            if len(out) == n:
                return out
            if item["concept_id"] != concept or item["id"] in seen:
                continue
            puzzle = Puzzle(
                user_id=user.id,
                source="seed",
                seed_id=item["id"],
                concept_id=concept,
                board_size=item["board_size"],
                setup=item["setup"],
                correct_moves=item["correct_moves"],
                solution_line=item["solution_line"],
                learner_moves=item["learner_moves"],
            )
            session.add(puzzle)
            session.add(fsrs_service.new_card(user.id, puzzle.id, now))
            out.append(puzzle)
    return out


def queue(
    session: Session, user: User, now: datetime, context: Context, limit: int = MAX_DUE
) -> list[Puzzle]:
    """Today's puzzles: due cards first, topped up with new seed puzzles."""
    limit = max(1, min(limit, MAX_DUE))
    puzzles = _due(session, user.id, now, limit)
    want = min(MIN_WARMUP, limit) if context == "warmup" else limit
    puzzles += serve_seeds(session, user, now, want - len(puzzles))
    session.commit()
    return puzzles


def add_card(session: Session, puzzle: Puzzle, now: datetime) -> None:
    """Schedule an own-mistake puzzle (once): first due the next day."""
    exists = session.exec(select(SrsCard.id).where(SrsCard.puzzle_id == puzzle.id)).first()
    if exists is None:
        session.add(fsrs_service.new_card(puzzle.user_id, puzzle.id, now + FIRST_DUE))


# -- attempts -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Graded:
    correct: bool
    done: bool
    solved: bool
    opponent_reply: str | None = None
    solution_line: list[str] | None = None
    rating: Rating | None = None
    next_due_at: datetime | None = None


def grade(puzzle: Puzzle, moves: list[str]) -> tuple[bool, bool, str | None]:
    """Judge the learner's last move. `moves` alternates learner and opponent, ending with the
    learner's. Returns (correct, done, opponent reply)."""
    if not moves or len(moves) % 2 == 0:
        raise BadMoves("the sequence must end with the learner's move")
    size = puzzle.board_size
    state = puzzle_state(puzzle)
    for gtp in moves[:-1]:
        p = _pt(gtp, size)
        if check_move(state, p) is not Legality.OK:
            raise BadMoves(f"illegal move in the sequence: {gtp}")
        state = play(state, p)
    last = _pt(moves[-1], size)
    if check_move(state, last) is not Legality.OK:
        return False, False, None
    turn = len(moves) // 2  # the learner's move number, from 0
    after = play(state, last)
    target = puzzle.setup.get("target")
    if turn == 0:
        if moves[-1] not in puzzle.correct_moves:
            return False, False, None
    elif not (target and chase_holds(after.board, _pt(target, size))):
        return False, False, None
    if turn + 1 >= puzzle.learner_moves or not target:
        return True, True, None
    reply = defender_reply(after.board, _pt(target, size))
    if reply is None or check_move(after, reply) is not Legality.OK:
        return True, True, None  # captured, or nowhere to run
    return True, False, point_to_gtp(reply, size)


def finish(
    session: Session,
    puzzle: Puzzle,
    outcome: Outcome,
    context: Context,
    now: datetime,
) -> tuple[Rating, datetime | None]:
    """Record the attempt and reschedule the card (exam attempts don't touch the schedule)."""
    result = rating(outcome)
    session.add(
        PuzzleAttempt(
            user_id=puzzle.user_id,
            puzzle_id=puzzle.id,
            context=context,
            result=result,
            hints_used=outcome.hints_used,
            time_ms=outcome.time_ms,
        )
    )
    due = None
    if context != "exam":
        card = session.exec(select(SrsCard).where(SrsCard.puzzle_id == puzzle.id)).first()
        if card is None:
            card = fsrs_service.new_card(puzzle.user_id, puzzle.id, now)
        fsrs_service.review(card, result, now)
        session.add(card)
        due = card.due_at
    session.commit()
    return result, due


def attempt(
    session: Session,
    puzzle: Puzzle,
    moves: list[str],
    *,
    hints_used: int,
    time_ms: int | None,
    wrong_tries: int,
    context: Context,
    now: datetime,
) -> Graded:
    correct, done, reply = grade(puzzle, moves)
    if not correct:
        if wrong_tries + 1 < FAILED_TRIES:
            return Graded(correct=False, done=False, solved=False)
        outcome = Outcome(False, wrong_tries + 1, hints_used, time_ms)
        result, due = finish(session, puzzle, outcome, context, now)
        return Graded(False, True, False, None, list(puzzle.solution_line), result, due)
    if not done:
        return Graded(correct=True, done=False, solved=False, opponent_reply=reply)
    outcome = Outcome(True, wrong_tries, hints_used, time_ms)
    result, due = finish(session, puzzle, outcome, context, now)
    return Graded(True, True, True, None, list(puzzle.solution_line), result, due)


def give_up(
    session: Session,
    puzzle: Puzzle,
    *,
    hints_used: int,
    time_ms: int | None,
    wrong_tries: int,
    context: Context,
    now: datetime,
) -> tuple[Rating, datetime | None]:
    """The learner asked for the answer (hint level 3): a failed review."""
    return finish(session, puzzle, Outcome(False, wrong_tries, hints_used, time_ms), context, now)
