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
