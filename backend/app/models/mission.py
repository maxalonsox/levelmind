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
    from app.models.stage import Stage
    from app.models.task import Task


class Mission(Base):
    __tablename__ = "missions"
    __table_args__ = (
        CheckConstraint("order_index >= 0", name="ck_missions_order_index"),
        CheckConstraint(
            "estimated_difficulty IS NULL OR "
            "estimated_difficulty IN ('easy', 'normal', 'difficult')",
            name="ck_missions_estimated_difficulty",
        ),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'skipped')",
            name="ck_missions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_difficulty: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PlanningStatus.PENDING,
        server_default=PlanningStatus.PENDING.value,
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

    stage: Mapped["Stage"] = relationship(back_populates="missions")
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
