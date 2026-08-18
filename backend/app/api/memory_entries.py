from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.schemas.memory_entry import MemoryEntryCreate, MemoryEntryResponse
from app.services.memory_entry import create_memory_entry, list_memory_entries

router = APIRouter(prefix="/memory-entries", tags=["memory"])


@router.post(
    "",
    response_model=MemoryEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_memory_entry_endpoint(
    data: MemoryEntryCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MemoryEntryResponse:
    entry = create_memory_entry(db, data, current_user.id)
    return MemoryEntryResponse.model_validate(entry)


@router.get("", response_model=list[MemoryEntryResponse])
def list_memory_entries_endpoint(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    goal_id: Annotated[UUID | None, Query()] = None,
) -> list[MemoryEntryResponse]:
    entries = list_memory_entries(db, current_user.id, goal_id=goal_id)
    return [MemoryEntryResponse.model_validate(entry) for entry in entries]
