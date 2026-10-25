"""m3 full games: final score and bot winrate per move

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("games") as batch:
        batch.add_column(sa.Column("final_score", sa.JSON(), nullable=True))
    with op.batch_alter_table("moves") as batch:
        batch.add_column(sa.Column("bot_winrate", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("moves") as batch:
        batch.drop_column("bot_winrate")
    with op.batch_alter_table("games") as batch:
        batch.drop_column("final_score")
