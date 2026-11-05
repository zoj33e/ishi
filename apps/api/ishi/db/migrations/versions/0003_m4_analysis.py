"""m4 analysis: per-move KataGo analyses, Why Engine mistakes, games.reviewed_at

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("updated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
    ]


def upgrade() -> None:
    with op.batch_alter_table("games") as batch:
        batch.add_column(
            sa.Column("reviewed_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True)
        )
    op.create_table(
        "analyses",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), primary_key=True),
        sa.Column(
            "user_id", sqlmodel.sql.sqltypes.AutoString(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "game_id", sqlmodel.sql.sqltypes.AutoString(), sa.ForeignKey("games.id"), nullable=False
        ),
        sa.Column("move_number", sa.Integer(), nullable=False),
        sa.Column("visits", sa.Integer(), nullable=False),
        sa.Column("root", sa.JSON(), nullable=False),
        sa.Column("move_infos", sa.JSON(), nullable=False),
        sa.Column("ownership", sa.JSON(), nullable=True),
        sa.Column("human_policy", sa.JSON(), nullable=True),
        sa.Column("engine_version", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_analyses_game_move", "analyses", ["game_id", "move_number"], unique=True)
    op.create_table(
        "mistakes",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), primary_key=True),
        sa.Column(
            "user_id", sqlmodel.sql.sqltypes.AutoString(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "game_id", sqlmodel.sql.sqltypes.AutoString(), sa.ForeignKey("games.id"), nullable=False
        ),
        sa.Column("move_number", sa.Integer(), nullable=False),
        sa.Column("points_lost", sa.Float(), nullable=False),
        sa.Column("concept_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("secondary_concepts", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("p_find", sa.Float(), nullable=True),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_mistakes_game_move", "mistakes", ["game_id", "move_number"], unique=True)
    op.create_index("ix_mistakes_concept", "mistakes", ["concept_id"])


def downgrade() -> None:
    op.drop_index("ix_mistakes_concept", "mistakes")
    op.drop_index("ix_mistakes_game_move", "mistakes")
    op.drop_table("mistakes")
    op.drop_index("ix_analyses_game_move", "analyses")
    op.drop_table("analyses")
    with op.batch_alter_table("games") as batch:
        batch.drop_column("reviewed_at")
