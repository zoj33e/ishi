"""SQLModel tables (07-data-model). Every table has id, user_id, created_at, updated_at.

Tables are added per milestone; M2 brings users, lesson progress, games, moves and exams.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Column, Index
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class _Timestamps(SQLModel):
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class User(_Timestamps, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=_uuid, primary_key=True)
    display_name: str = ""
    locale: str = "th"
    belt: str = "white"
    rank_estimate: float | None = None
    bot_rank: float | None = None
    settings: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class LessonProgress(_Timestamps, table=True):
    __tablename__ = "lesson_progress"
    __table_args__ = (Index("ix_lesson_progress_user_lesson", "user_id", "lesson_id", unique=True),)

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id")
    lesson_id: str
    status: str = "locked"  # locked / available / done
    attempts: int = 0
    tasks_done: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class Exam(_Timestamps, table=True):
    __tablename__ = "exams"

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id")
    belt_target: str
    status: str = "in_progress"  # in_progress / passed / failed
    puzzle_score: int | None = None
    games_won: int = 0
    games_lost: int = 0


class Game(_Timestamps, table=True):
    __tablename__ = "games"

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    mode: str  # capture / full / exam
    board_size: int
    rules: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    komi: float = 7.0
    learner_color: str = "black"
    bot_kind: str  # capture_bot / humansl
    bot_rank: float | None = None
    bot_params: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = "active"  # active / finished / abandoned
    result: str | None = None
    learner_won: bool | None = None
    sgf: str = ""
    nudges_used: int = 0
    exam_id: str | None = Field(default=None, foreign_key="exams.id")
    # Full games: {black_area, white_area, komi, dead: [GTP], katago_lead} after two passes.
    final_score: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    reviewed_at: datetime | None = None  # Why Engine review done (M4)


class Move(_Timestamps, table=True):
    __tablename__ = "moves"
    __table_args__ = (Index("ix_moves_game_number", "game_id", "number", unique=True),)

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id")
    game_id: str = Field(foreign_key="games.id")
    number: int  # 1-based
    color: str  # black / white
    point: str | None  # GTP, None = pass
    captures: int = 0
    by_learner: bool
    nudge_shown: bool = False
    played_anyway: bool = False
    bot_winrate: float | None = None  # full games: the bot's winrate before its move (resign rule)


class Analysis(_Timestamps, table=True):
    """KataGo's view of the position after `move_number` moves (0 = empty board)."""

    __tablename__ = "analyses"
    __table_args__ = (Index("ix_analyses_game_move", "game_id", "move_number", unique=True),)

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id")
    game_id: str = Field(foreign_key="games.id")
    move_number: int
    visits: int
    root: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))  # raw, Black perspective
    move_infos: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))  # top 12
    ownership: list[float] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    human_policy: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    engine_version: str = ""


class Mistake(_Timestamps, table=True):
    """A learner move the Why Engine explained (or flagged `unexplained`)."""

    __tablename__ = "mistakes"
    __table_args__ = (
        Index("ix_mistakes_game_move", "game_id", "move_number", unique=True),
        Index("ix_mistakes_concept", "concept_id"),
    )

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id")
    game_id: str = Field(foreign_key="games.id")
    move_number: int
    points_lost: float
    concept_id: str
    secondary_concepts: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    evidence: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))  # the ConceptHit
    p_find: float | None = None
    eligible: bool = False


class Lesson(_Timestamps, table=True):
    """The one post-game lesson of a game (M5): a mistake, a praise moment or a clean-game note."""

    __tablename__ = "lessons"
    __table_args__ = (Index("ix_lessons_game", "game_id", unique=True),)

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    game_id: str = Field(foreign_key="games.id")
    mistake_id: str | None = Field(default=None, foreign_key="mistakes.id")
    lesson_type: str  # mistake / praise / clean
    concept_id: str | None = None
    move_number: int | None = None  # the learner's move the lesson is about
    fact_package: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    narration: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    narration_source: str  # llm / template
    llm_reject_reason: str | None = None
    solution_line: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    attempts: int = 0  # retry moves played
    hint_level: int = 0  # highest hint shown: 1 question, 2 area, 3 solution
    retry_result: str | None = None  # solved_first / solved_hint / failed
    viewed_at: datetime | None = None
    done_at: datetime | None = None


class Puzzle(_Timestamps, table=True):
    """A Shape Gym position (M5 creates them from lessons; M6 schedules them)."""

    __tablename__ = "puzzles"
    __table_args__ = (Index("ix_puzzles_seed", "user_id", "seed_id", unique=True),)

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    source: str  # own_mistake / seed
    concept_id: str
    board_size: int
    # {black: [GTP], white: [GTP], to_move: black|white, komi, rules}
    setup: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    correct_moves: list[str] = Field(sa_column=Column(JSON, nullable=False))
    solution_line: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    difficulty: float | None = None
    origin_lesson_id: str | None = Field(default=None, foreign_key="lessons.id")
    seed_id: str | None = None  # content/puzzles id for source=seed
    learner_moves: int = 1  # moves the learner plays to solve it (the opponent answers between)


class SrsCard(_Timestamps, table=True):
    """A puzzle's FSRS schedule (one card per puzzle)."""

    __tablename__ = "srs_cards"
    __table_args__ = (
        Index("ix_srs_cards_puzzle", "puzzle_id", unique=True),
        Index("ix_srs_cards_due", "user_id", "due_at"),
    )

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id")
    puzzle_id: str = Field(foreign_key="puzzles.id")
    fsrs_state: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    due_at: datetime
    reps: int = 0
    lapses: int = 0


class PuzzleAttempt(_Timestamps, table=True):
    __tablename__ = "puzzle_attempts"

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    puzzle_id: str = Field(foreign_key="puzzles.id")
    context: str  # warmup / gym / exam
    result: str  # again / hard / good / easy
    hints_used: int = 0
    time_ms: int | None = None


class NarrationCache(_Timestamps, table=True):
    """Validated model narrations by FactPackage hash (06: the same facts reuse the same text)."""

    __tablename__ = "narration_cache"
    __table_args__ = (Index("ix_narration_cache_key", "user_id", "key", unique=True),)

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id")
    key: str
    narration: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    model: str
