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
