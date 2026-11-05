"""m6 shape gym: spaced-repetition cards, puzzle attempts, seed puzzles

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STR = sqlmodel.sql.sqltypes.AutoString
TIME = sqlmodel.sql.sqltypes.UTCDateTime


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TIME(), nullable=False),
        sa.Column("updated_at", TIME(), nullable=False),
    ]


def _fk(name: str, table: str) -> sa.Column:
    return sa.Column(name, STR(), sa.ForeignKey(f"{table}.id"), nullable=False)


def upgrade() -> None:
    with op.batch_alter_table("puzzles") as batch:
        batch.add_column(sa.Column("seed_id", STR(), nullable=True))
        batch.add_column(
            sa.Column("learner_moves", sa.Integer(), nullable=False, server_default="1")
        )
    op.create_index("ix_puzzles_seed", "puzzles", ["user_id", "seed_id"], unique=True)
    op.create_table(
        "srs_cards",
        sa.Column("id", STR(), primary_key=True),
        _fk("user_id", "users"),
        _fk("puzzle_id", "puzzles"),
        sa.Column("fsrs_state", sa.JSON(), nullable=False),
        sa.Column("due_at", TIME(), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("lapses", sa.Integer(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_srs_cards_puzzle", "srs_cards", ["puzzle_id"], unique=True)
    op.create_index("ix_srs_cards_due", "srs_cards", ["user_id", "due_at"])
    op.create_table(
        "puzzle_attempts",
        sa.Column("id", STR(), primary_key=True),
        _fk("user_id", "users"),
        _fk("puzzle_id", "puzzles"),
        sa.Column("context", STR(), nullable=False),
        sa.Column("result", STR(), nullable=False),
        sa.Column("hints_used", sa.Integer(), nullable=False),
        sa.Column("time_ms", sa.Integer(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_puzzle_attempts_user_id", "puzzle_attempts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_puzzle_attempts_user_id", "puzzle_attempts")
    op.drop_table("puzzle_attempts")
    op.drop_index("ix_srs_cards_due", "srs_cards")
    op.drop_index("ix_srs_cards_puzzle", "srs_cards")
    op.drop_table("srs_cards")
    op.drop_index("ix_puzzles_seed", "puzzles")
    with op.batch_alter_table("puzzles") as batch:
        batch.drop_column("learner_moves")
        batch.drop_column("seed_id")
