"""enforce one active goal per user

Revision ID: c9d2e4f6a8b0
Revises: b8f1c2d3e4a5
Create Date: 2026-08-18 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c9d2e4f6a8b0"
down_revision: str | None = "b8f1c2d3e4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_goals_user_id_active",
        "goals",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_goals_user_id_active", table_name="goals")
