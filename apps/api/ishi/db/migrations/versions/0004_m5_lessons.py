"""m5 lessons: post-game lessons, Shape Gym puzzles, narration cache

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STR = sqlmodel.sql.sqltypes.AutoString


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("updated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
    ]


def _fk(name: str, table: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, STR(), sa.ForeignKey(f"{table}.id"), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "lessons",
        sa.Column("id", STR(), primary_key=True),
        _fk("user_id", "users"),
        _fk("game_id", "games"),
        _fk("mistake_id", "mistakes", nullable=True),
        sa.Column("lesson_type", STR(), nullable=False),
        sa.Column("concept_id", STR(), nullable=True),
        sa.Column("move_number", sa.Integer(), nullable=True),
        sa.Column("fact_package", sa.JSON(), nullable=False),
        sa.Column("narration", sa.JSON(), nullable=False),
        sa.Column("narration_source", STR(), nullable=False),
        sa.Column("llm_reject_reason", STR(), nullable=True),
        sa.Column("solution_line", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("hint_level", sa.Integer(), nullable=False),
        sa.Column("retry_result", STR(), nullable=True),
        sa.Column("viewed_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        sa.Column("done_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_lessons_game", "lessons", ["game_id"], unique=True)
    op.create_index("ix_lessons_user_id", "lessons", ["user_id"])
    op.create_table(
        "puzzles",
        sa.Column("id", STR(), primary_key=True),
        _fk("user_id", "users"),
        sa.Column("source", STR(), nullable=False),
        sa.Column("concept_id", STR(), nullable=False),
        sa.Column("board_size", sa.Integer(), nullable=False),
        sa.Column("setup", sa.JSON(), nullable=False),
        sa.Column("correct_moves", sa.JSON(), nullable=False),
        sa.Column("solution_line", sa.JSON(), nullable=False),
        sa.Column("difficulty", sa.Float(), nullable=True),
        _fk("origin_lesson_id", "lessons", nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_puzzles_user_id", "puzzles", ["user_id"])
    op.create_table(
        "narration_cache",
        sa.Column("id", STR(), primary_key=True),
        _fk("user_id", "users"),
        sa.Column("key", STR(), nullable=False),
        sa.Column("narration", sa.JSON(), nullable=False),
        sa.Column("model", STR(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_narration_cache_key", "narration_cache", ["user_id", "key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_narration_cache_key", "narration_cache")
    op.drop_table("narration_cache")
    op.drop_index("ix_puzzles_user_id", "puzzles")
    op.drop_table("puzzles")
    op.drop_index("ix_lessons_user_id", "lessons")
    op.drop_index("ix_lessons_game", "lessons")
    op.drop_table("lessons")
