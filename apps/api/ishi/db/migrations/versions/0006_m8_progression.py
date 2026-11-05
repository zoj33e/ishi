"""m8 progression: rank history, per-game move likelihood, exam puzzles

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STR = sqlmodel.sql.sqltypes.AutoString
TIME = sqlmodel.sql.sqltypes.UTCDateTime


def upgrade() -> None:
    with op.batch_alter_table("games") as batch:
        batch.add_column(sa.Column("likelihood", sa.JSON(), nullable=True))
    with op.batch_alter_table("exams") as batch:
        batch.add_column(sa.Column("puzzles", sa.JSON(), nullable=False, server_default="[]"))
    op.create_table(
        "rank_history",
        sa.Column("id", STR(), primary_key=True),
        sa.Column("user_id", STR(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("rank_estimate", sa.Float(), nullable=False),
        sa.Column("likelihood_rank", sa.Float(), nullable=True),
        sa.Column("results_rank", sa.Float(), nullable=True),
        sa.Column("games_count", sa.Integer(), nullable=False),
        sa.Column("created_at", TIME(), nullable=False),
        sa.Column("updated_at", TIME(), nullable=False),
    )
    op.create_index("ix_rank_history_user_date", "rank_history", ["user_id", "date"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_rank_history_user_date", "rank_history")
    op.drop_table("rank_history")
    with op.batch_alter_table("exams") as batch:
        batch.drop_column("puzzles")
    with op.batch_alter_table("games") as batch:
        batch.drop_column("likelihood")
