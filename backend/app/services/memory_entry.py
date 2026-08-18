from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import MemoryType
from app.models.memory_entry import MemoryEntry
from app.schemas.memory_entry import MemoryEntryCreate
from app.services.goal import get_owned_goal

RECENT_TASK_EXECUTION_MEMORY_LIMIT = 10


def create_memory_entry(
    db: Session,
    data: MemoryEntryCreate,
    user_id: UUID,
) -> MemoryEntry:
    try:
        entry = add_memory_entry(db, data, user_id)
        db.commit()
        db.refresh(entry)
        return entry
    except Exception:
        db.rollback()
        raise


def add_memory_entry(
    db: Session,
    data: MemoryEntryCreate,
    user_id: UUID,
) -> MemoryEntry:
    if data.goal_id is not None:
        get_owned_goal(db, data.goal_id, user_id)

    entry = MemoryEntry(
        user_id=user_id,
        goal_id=data.goal_id,
        memory_type=data.memory_type,
        key=data.key,
        value=data.value,
        source_type=data.source_type,
        source_id=data.source_id,
        confidence=data.confidence,
    )
    db.add(entry)
    db.flush()
    return entry


def list_memory_entries(
    db: Session,
    user_id: UUID,
    *,
    goal_id: UUID | None = None,
) -> list[MemoryEntry]:
    if goal_id is not None:
        get_owned_goal(db, goal_id, user_id)

    statement = select(MemoryEntry).where(MemoryEntry.user_id == user_id)
    if goal_id is not None:
        statement = statement.where(MemoryEntry.goal_id == goal_id)

    return list(db.scalars(statement.order_by(MemoryEntry.created_at, MemoryEntry.id)))


def list_recent_task_execution_memories(
    db: Session,
    user_id: UUID,
    goal_id: UUID,
) -> list[MemoryEntry]:
    get_owned_goal(db, goal_id, user_id)
    statement = (
        select(MemoryEntry)
        .where(
            MemoryEntry.user_id == user_id,
            MemoryEntry.goal_id == goal_id,
            MemoryEntry.memory_type == MemoryType.OBSERVED,
            MemoryEntry.key == "task_execution",
        )
        .order_by(MemoryEntry.created_at.desc(), MemoryEntry.id.desc())
        .limit(RECENT_TASK_EXECUTION_MEMORY_LIMIT)
    )
    return list(db.scalars(statement))
