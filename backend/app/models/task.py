import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PlanningStatus

if TYPE_CHECKING:
    from app.models.mission import Mission


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("order_index >= 0", name="ck_tasks_order_index"),
        CheckConstraint(
            "estimated_duration_minutes IS NULL OR estimated_duration_minutes > 0",
            name="ck_tasks_estimated_duration_minutes",
        ),
        CheckConstraint(
            "estimated_difficulty IS NULL OR "
            "estimated_difficulty IN ('easy', 'normal', 'difficult')",
            name="ck_tasks_estimated_difficulty",
        ),
        CheckConstraint("xp_reward >= 0", name="ck_tasks_xp_reward"),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'skipped')",
            name="ck_tasks_status",
        ),
        CheckConstraint(
            "difficulty_feedback IS NULL OR "
            "difficulty_feedback IN ('easy', 'normal', 'difficult')",
            name="ck_tasks_difficulty_feedback",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("missions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    estimated_difficulty: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PlanningStatus.PENDING,
        server_default=PlanningStatus.PENDING.value,
    )
    difficulty_feedback: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    xp_reward: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, server_default="10"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    mission: Mapped["Mission"] = relationship(back_populates="tasks")
