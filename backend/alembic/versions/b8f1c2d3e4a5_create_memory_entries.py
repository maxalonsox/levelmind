"""create memory entries

Revision ID: b8f1c2d3e4a5
Revises: e4a9c7d21b63
Create Date: 2026-08-17 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b8f1c2d3e4a5"
down_revision: str | None = "e4a9c7d21b63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("goal_id", sa.UUID(), nullable=True),
        sa.Column("memory_type", sa.String(length=20), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "memory_type IN ('declared', 'observed')",
            name="ck_memory_entries_memory_type",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_memory_entries_confidence",
        ),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_memory_entries_goal_id"),
        "memory_entries",
        ["goal_id"],
    )
    op.create_index(
        op.f("ix_memory_entries_user_id"),
        "memory_entries",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_memory_entries_user_id"), table_name="memory_entries"
    )
    op.drop_index(
        op.f("ix_memory_entries_goal_id"), table_name="memory_entries"
    )
    op.drop_table("memory_entries")
