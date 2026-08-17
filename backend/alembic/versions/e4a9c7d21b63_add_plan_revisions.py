"""add plan revisions

Revision ID: e4a9c7d21b63
Revises: d3f6a8b91c42
Create Date: 2026-08-17 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e4a9c7d21b63"
down_revision: str | None = "d3f6a8b91c42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "estimated_difficulty", sa.String(length=20), nullable=True
        ),
    )
    op.create_check_constraint(
        "ck_tasks_estimated_difficulty",
        "tasks",
        "estimated_difficulty IS NULL OR "
        "estimated_difficulty IN ('easy', 'normal', 'difficult')",
    )

    op.create_table(
        "plan_revisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("goal_id", sa.UUID(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("base_revision_id", sa.UUID(), nullable=True),
        sa.Column("adaptation_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision_number > 0",
            name="ck_plan_revisions_revision_number",
        ),
        sa.ForeignKeyConstraint(
            ["adaptation_id"], ["plan_adaptations.id"]
        ),
        sa.ForeignKeyConstraint(
            ["base_revision_id"], ["plan_revisions.id"]
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"], ["goals.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "adaptation_id", name="uq_plan_revisions_adaptation_id"
        ),
        sa.UniqueConstraint(
            "goal_id",
            "revision_number",
            name="uq_plan_revisions_goal_revision_number",
        ),
    )

    op.add_column(
        "plan_adaptations",
        sa.Column("base_revision_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_plan_adaptations_base_revision_id_plan_revisions",
        "plan_adaptations",
        "plan_revisions",
        ["base_revision_id"],
        ["id"],
    )
    op.create_index(
        "ix_plan_adaptations_base_revision_id",
        "plan_adaptations",
        ["base_revision_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_plan_adaptations_base_revision_id",
        table_name="plan_adaptations",
    )
    op.drop_constraint(
        "fk_plan_adaptations_base_revision_id_plan_revisions",
        "plan_adaptations",
        type_="foreignkey",
    )
    op.drop_column("plan_adaptations", "base_revision_id")
    op.drop_table("plan_revisions")
    op.drop_constraint(
        "ck_tasks_estimated_difficulty", "tasks", type_="check"
    )
    op.drop_column("tasks", "estimated_difficulty")
