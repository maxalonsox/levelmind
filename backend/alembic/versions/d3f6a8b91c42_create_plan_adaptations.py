"""create plan adaptations

Revision ID: d3f6a8b91c42
Revises: a71c9e42d6f0
Create Date: 2026-08-17 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d3f6a8b91c42"
down_revision: str | None = "a71c9e42d6f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plan_adaptations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("goal_id", sa.UUID(), nullable=False),
        sa.Column("proposal", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "reviewed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_plan_adaptations_status",
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"], ["goals.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_plan_adaptations_goal_id",
        "plan_adaptations",
        ["goal_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_plan_adaptations_goal_id", table_name="plan_adaptations"
    )
    op.drop_table("plan_adaptations")
