"""m2 users lessons games moves exams

Revision ID: 0001
Revises:
Create Date: 2026-10-25 21:29:57.066465
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.create_table(
        "users",
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("updated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("display_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("locale", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("belt", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("rank_estimate", sa.Float(), nullable=True),
        sa.Column("bot_rank", sa.Float(), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "exams",
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("updated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("belt_target", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("puzzle_score", sa.Integer(), nullable=True),
        sa.Column("games_won", sa.Integer(), nullable=False),
        sa.Column("games_lost", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "lesson_progress",
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("updated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("lesson_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("tasks_done", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lesson_progress", schema=None) as batch_op:
        batch_op.create_index(
            "ix_lesson_progress_user_lesson", ["user_id", "lesson_id"], unique=True
        )

    op.create_table(
        "games",
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("updated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("mode", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("board_size", sa.Integer(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("komi", sa.Float(), nullable=False),
        sa.Column("learner_color", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("bot_kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("bot_rank", sa.Float(), nullable=True),
        sa.Column("bot_params", sa.JSON(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("result", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("learner_won", sa.Boolean(), nullable=True),
        sa.Column("sgf", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("nudges_used", sa.Integer(), nullable=False),
        sa.Column("exam_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("games", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_games_user_id"), ["user_id"], unique=False)

    op.create_table(
        "moves",
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("updated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("game_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("color", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("point", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("captures", sa.Integer(), nullable=False),
        sa.Column("by_learner", sa.Boolean(), nullable=False),
        sa.Column("nudge_shown", sa.Boolean(), nullable=False),
        sa.Column("played_anyway", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("moves", schema=None) as batch_op:
        batch_op.create_index("ix_moves_game_number", ["game_id", "number"], unique=True)


def downgrade() -> None:

    with op.batch_alter_table("moves", schema=None) as batch_op:
        batch_op.drop_index("ix_moves_game_number")

    op.drop_table("moves")
    with op.batch_alter_table("games", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_games_user_id"))

    op.drop_table("games")
    with op.batch_alter_table("lesson_progress", schema=None) as batch_op:
        batch_op.drop_index("ix_lesson_progress_user_lesson")

    op.drop_table("lesson_progress")
    op.drop_table("exams")
    op.drop_table("users")
