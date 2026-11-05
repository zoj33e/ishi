"""Capture Go stages (D-024) and the White -> Yellow exam rules (D-023). Pure functions, no I/O.

Callers pass finished games oldest first; the stage is always recomputed from history, so there
is no stored counter to drift.
"""

from __future__ import annotations

from dataclasses import dataclass

STREAK_TO_ADVANCE = 3
EXAM_MIN_CAPTURE_GAMES = 5
EXAM_RETRY_GAMES = 3
EXAM_WINS_TO_PASS = 3
EXAM_LOSSES_TO_FAIL = 3


@dataclass(frozen=True)
class Stage:
    number: int  # 1-based
    board_size: int
    target: int  # captures needed to win
    level: int  # capture bot level


STAGES = (
    Stage(1, 7, 1, 1),
    Stage(2, 9, 1, 1),
    Stage(3, 9, 3, 1),
    Stage(4, 9, 3, 2),
    Stage(5, 9, 3, 3),
)

EXAM_STAGE = Stage(0, 9, 3, 2)  # Yellow exam games: 9x9, first to 3, level 2


@dataclass(frozen=True)
class PlayedGame:
    stage: int  # Stage.number the game was played at
    won: bool


@dataclass(frozen=True)
class StageStatus:
    stage: Stage
    streak: int  # wins in a row at this stage
    games_played: int


def current_stage(history: list[PlayedGame]) -> StageStatus:
    idx, streak = 0, 0
    for g in history:
        if g.stage != STAGES[idx].number:
            continue  # played at an older stage (e.g. before an advance)
        if g.won:
            streak += 1
            if streak >= STREAK_TO_ADVANCE and idx < len(STAGES) - 1:
                idx, streak = idx + 1, 0
        else:
            streak = 0
    return StageStatus(STAGES[idx], streak, len(history))


@dataclass(frozen=True)
class ExamRecord:
    status: str  # in_progress / passed / failed
    games_after: int  # non-exam capture games finished after this exam ended


def exam_available(
    belt: str,
    lessons_done: bool,
    capture_games: int,
    exams: list[ExamRecord],
) -> bool:
    """White -> Yellow: school done, >= 5 capture games, and 3 more games after a failed try."""
    if belt != "white" or not lessons_done or capture_games < EXAM_MIN_CAPTURE_GAMES:
        return False
    if any(e.status in ("in_progress", "passed") for e in exams):
        return False
    if exams and exams[-1].status == "failed":
        return exams[-1].games_after >= EXAM_RETRY_GAMES
    return True


def exam_outcome(won: int, lost: int) -> str:
    """Draws count as losses (D-027)."""
    if won >= EXAM_WINS_TO_PASS:
        return "passed"
    if lost >= EXAM_LOSSES_TO_FAIL:
        return "failed"
    return "in_progress"


# -- belt exams Orange -> Brown (M8, 02-curriculum) ---------------------------------------

NEXT_BELT = {
    "yellow": "orange",
    "orange": "green",
    "green": "blue",
    "blue": "purple",
    "purple": "brown",
}
BELT_EXAM_PUZZLES = 12
BELT_EXAM_PUZZLES_TO_PASS = 10
BELT_EXAM_WINS = 2  # best of 3
BELT_EXAM_LOSSES = 2
BELT_EXAM_RANK_MARGIN = 2.0  # the estimate within 2 stones of the next belt's rank
BELT_EXAM_MIN_GAMES = 5  # 9x9 games since the last belt


def belt_exam_available(
    belt: str,
    rank_estimate: float | None,
    belt_rank: float | None,
    games_since_belt: int,
    exams: list[ExamRecord],
) -> bool:
    """Next-belt exam: close enough in rank, enough games, 3 more games after a failed try.

    `belt_rank` is the next belt's rank; `exams` are this belt's earlier tries, oldest first."""
    if belt not in NEXT_BELT or rank_estimate is None or belt_rank is None:
        return False
    if rank_estimate > belt_rank + BELT_EXAM_RANK_MARGIN:
        return False
    if games_since_belt < BELT_EXAM_MIN_GAMES:
        return False
    if any(e.status in ("in_progress", "passed") for e in exams):
        return False
    if exams and exams[-1].status == "failed":
        return exams[-1].games_after >= EXAM_RETRY_GAMES
    return True


def belt_exam_games_left(games_since_belt: int, exams: list[ExamRecord]) -> int:
    """Games still to play before the next-belt exam opens (the rank rule aside)."""
    left = BELT_EXAM_MIN_GAMES - games_since_belt
    if exams and exams[-1].status == "failed":
        left = max(left, EXAM_RETRY_GAMES - exams[-1].games_after)
    return max(0, left)


def belt_exam_outcome(puzzles: list[bool | None], won: int, lost: int) -> str:
    """Puzzles first: once 10 of 12 can no longer be reached the exam is failed; then best of 3
    games (draws count as losses)."""
    wrong = sum(1 for s in puzzles if s is False)
    if wrong > len(puzzles) - BELT_EXAM_PUZZLES_TO_PASS:
        return "failed"
    if won >= BELT_EXAM_WINS:
        return "passed"
    if lost >= BELT_EXAM_LOSSES:
        return "failed"
    return "in_progress"


def belt_exam_phase(puzzles: list[bool | None], status: str) -> str:
    """`puzzles` until every puzzle is answered, then `games`; `done` once decided."""
    if status != "in_progress":
        return "done"
    return "puzzles" if any(s is None for s in puzzles) else "games"
