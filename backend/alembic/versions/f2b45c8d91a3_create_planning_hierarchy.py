"""create planning hierarchy

Revision ID: f2b45c8d91a3
Revises: 84cdcf9b2bc7
Create Date: 2026-08-17 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f2b45c8d91a3"
down_revision: str | None = "84cdcf9b2bc7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("goal_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("order_index >= 0", name="ck_stages_order_index"),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'skipped')",
            name="ck_stages_status",
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"], ["goals.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stages_goal_id", "stages", ["goal_id"])

    op.create_table(
        "missions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("stage_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("estimated_difficulty", sa.String(length=20), nullable=True),
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
        sa.CheckConstraint("order_index >= 0", name="ck_missions_order_index"),
        sa.CheckConstraint(
            "estimated_difficulty IS NULL OR "
            "estimated_difficulty IN ('easy', 'normal', 'difficult')",
            name="ck_missions_estimated_difficulty",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'skipped')",
            name="ck_missions_status",
        ),
        sa.ForeignKeyConstraint(
            ["stage_id"], ["stages.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_missions_stage_id", "missions", ["stage_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("mission_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("difficulty_feedback", sa.String(length=20), nullable=True),
        sa.Column("feedback_text", sa.Text(), nullable=True),
        sa.Column("xp_reward", sa.Integer(), server_default="10", nullable=False),
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
        sa.CheckConstraint("order_index >= 0", name="ck_tasks_order_index"),
        sa.CheckConstraint(
            "estimated_duration_minutes IS NULL OR estimated_duration_minutes > 0",
            name="ck_tasks_estimated_duration_minutes",
        ),
        sa.CheckConstraint("xp_reward >= 0", name="ck_tasks_xp_reward"),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'skipped')",
            name="ck_tasks_status",
        ),
        sa.CheckConstraint(
            "difficulty_feedback IS NULL OR "
            "difficulty_feedback IN ('easy', 'normal', 'difficult')",
            name="ck_tasks_difficulty_feedback",
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"], ["missions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_mission_id", "tasks", ["mission_id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_mission_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_missions_stage_id", table_name="missions")
    op.drop_table("missions")
    op.drop_index("ix_stages_goal_id", table_name="stages")
    op.drop_table("stages")
