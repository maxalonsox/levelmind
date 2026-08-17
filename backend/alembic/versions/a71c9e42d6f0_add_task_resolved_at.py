"""add task resolved at

Revision ID: a71c9e42d6f0
Revises: f2b45c8d91a3
Create Date: 2026-08-17 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a71c9e42d6f0"
down_revision: str | None = "f2b45c8d91a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "resolved_at")
