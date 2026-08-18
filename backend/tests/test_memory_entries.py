import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser, get_current_user
from app.db.base import Base
from app.main import app
from app.models.goal import Goal
from app.models.memory_entry import MemoryEntry
from app.services.memory_entry import (
    RECENT_TASK_EXECUTION_MEMORY_LIMIT,
    list_recent_task_execution_memories,
)


async def request_memory_entries(
    method: str,
    *,
    payload: dict[str, Any] | None = None,
    goal_id: UUID | None = None,
) -> Response:
    transport = ASGITransport(app=app)
    params = {"goal_id": str(goal_id)} if goal_id is not None else None
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(
            method,
            "/memory-entries",
            json=payload,
            params=params,
        )


def memory_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "memory_type": "observed",
        "key": "task_difficulty_pattern",
        "value": {
            "estimated_difficulty": "hard",
            "completed": 3,
            "skipped": 1,
        },
        "source_type": "task_result",
        "source_id": str(uuid4()),
        "confidence": 0.8,
    }
    payload.update(overrides)
    return payload


def add_goal(db: Session, user_id: UUID) -> Goal:
    goal = Goal(
        user_id=user_id,
        title="Learn backend development",
        current_situation="Python fundamentals",
        expected_outcome="Build production APIs",
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def test_create_global_memory_entry(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    payload = memory_payload(
        memory_type="declared",
        key="preferred_task_duration",
        value={"minutes": 30},
        source_type="user_input",
        source_id=None,
        confidence=1,
    )

    response = asyncio.run(request_memory_entries("POST", payload=payload))

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == str(authenticated_user_id)
    assert body["goal_id"] is None
    assert body["memory_type"] == "declared"
    assert body["value"] == {"minutes": 30}
    assert body["confidence"] == 1
    assert body["created_at"]

    persisted = db_session.scalar(select(MemoryEntry))
    assert persisted is not None
    assert persisted.user_id == authenticated_user_id
    assert persisted.key == "preferred_task_duration"


def test_create_goal_memory_validates_goal_ownership(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    owned_goal = add_goal(db_session, authenticated_user_id)
    other_goal = add_goal(db_session, uuid4())

    accepted = asyncio.run(
        request_memory_entries(
            "POST",
            payload=memory_payload(goal_id=str(owned_goal.id)),
        )
    )
    rejected = asyncio.run(
        request_memory_entries(
            "POST",
            payload=memory_payload(goal_id=str(other_goal.id)),
        )
    )

    assert accepted.status_code == 201
    assert accepted.json()["goal_id"] == str(owned_goal.id)
    assert rejected.status_code == 404
    assert db_session.scalar(
        select(MemoryEntry).where(MemoryEntry.goal_id == other_goal.id)
    ) is None


def test_list_memory_entries_isolated_by_user_and_filtered_by_goal(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = add_goal(db_session, authenticated_user_id)
    other_goal = add_goal(db_session, authenticated_user_id)
    entries = [
        MemoryEntry(
            user_id=authenticated_user_id,
            goal_id=None,
            memory_type="declared",
            key="global",
            value={"global": True},
            source_type="user_input",
            confidence=1,
        ),
        MemoryEntry(
            user_id=authenticated_user_id,
            goal_id=goal.id,
            memory_type="observed",
            key="selected_goal",
            value={"count": 2},
            source_type="task_result",
            confidence=0.75,
        ),
        MemoryEntry(
            user_id=authenticated_user_id,
            goal_id=other_goal.id,
            memory_type="observed",
            key="other_goal",
            value={"count": 1},
            source_type="task_result",
            confidence=0.5,
        ),
        MemoryEntry(
            user_id=uuid4(),
            goal_id=None,
            memory_type="declared",
            key="another_user",
            value={"private": True},
            source_type="user_input",
            confidence=1,
        ),
    ]
    db_session.add_all(entries)
    db_session.commit()

    all_response = asyncio.run(request_memory_entries("GET"))
    filtered_response = asyncio.run(
        request_memory_entries("GET", goal_id=goal.id)
    )

    assert all_response.status_code == 200
    assert {entry["key"] for entry in all_response.json()} == {
        "global",
        "selected_goal",
        "other_goal",
    }
    assert filtered_response.status_code == 200
    assert [entry["key"] for entry in filtered_response.json()] == [
        "selected_goal"
    ]


def test_list_memory_rejects_goal_owned_by_another_user(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    del authenticated_user_id
    other_goal = add_goal(db_session, uuid4())

    response = asyncio.run(request_memory_entries("GET", goal_id=other_goal.id))

    assert response.status_code == 404


def test_create_memory_entry_validates_contract(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    del authenticated_user_id

    invalid_type = asyncio.run(
        request_memory_entries(
            "POST", payload=memory_payload(memory_type="inferred")
        )
    )
    invalid_confidence = asyncio.run(
        request_memory_entries("POST", payload=memory_payload(confidence=1.1))
    )
    controlled_fields = asyncio.run(
        request_memory_entries(
            "POST",
            payload=memory_payload(user_id=str(uuid4()), id=str(uuid4())),
        )
    )

    assert invalid_type.status_code == 422
    assert invalid_confidence.status_code == 422
    assert controlled_fields.status_code == 422
    assert db_session.scalar(select(MemoryEntry)) is None


def test_memory_entries_require_authentication(db_session: Session) -> None:
    response = asyncio.run(
        request_memory_entries("POST", payload=memory_payload())
    )

    assert response.status_code == 401
    assert db_session.scalar(select(MemoryEntry)) is None


def test_memory_entries_do_not_expose_update_or_delete(
    authenticated_user_id: UUID,
) -> None:
    del authenticated_user_id

    update_response = asyncio.run(
        request_memory_entries("PUT", payload=memory_payload())
    )
    delete_response = asyncio.run(request_memory_entries("DELETE"))

    assert update_response.status_code == 405
    assert delete_response.status_code == 405


def test_service_cannot_read_another_users_memory(db_session: Session) -> None:
    first_user_id = uuid4()
    second_user_id = uuid4()
    entry = MemoryEntry(
        user_id=first_user_id,
        memory_type="declared",
        key="private_preference",
        value={"minutes": 20},
        source_type="user_input",
        confidence=1,
    )
    db_session.add(entry)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=second_user_id
    )
    try:
        response = asyncio.run(request_memory_entries("GET"))
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json() == []


def test_memory_table_is_registered_at_alembic_head() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("path_separator", "os")
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["b8f1c2d3e4a5"]
    table = Base.metadata.tables["memory_entries"]
    assert set(table.columns.keys()) == {
        "id",
        "user_id",
        "goal_id",
        "memory_type",
        "key",
        "value",
        "source_type",
        "source_id",
        "confidence",
        "created_at",
    }


def test_recent_task_execution_memory_is_owned_filtered_ordered_and_limited(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = add_goal(db_session, authenticated_user_id)
    other_goal = add_goal(db_session, authenticated_user_id)
    first_created_at = datetime(2026, 8, 1, tzinfo=UTC)
    matching_source_ids = [uuid4() for _ in range(12)]
    matching = [
        MemoryEntry(
            user_id=authenticated_user_id,
            goal_id=goal.id,
            memory_type="observed",
            key="task_execution",
            value={
                "result": "completed",
                "estimated_difficulty": "normal",
                "difficulty_feedback": "normal",
            },
            source_type="task",
            source_id=source_id,
            confidence=1,
            created_at=first_created_at + timedelta(minutes=index),
        )
        for index, source_id in enumerate(matching_source_ids)
    ]
    excluded = [
        MemoryEntry(
            user_id=authenticated_user_id,
            goal_id=other_goal.id,
            memory_type="observed",
            key="task_execution",
            value={"result": "skipped"},
            source_type="task",
            confidence=1,
        ),
        MemoryEntry(
            user_id=uuid4(),
            goal_id=goal.id,
            memory_type="observed",
            key="task_execution",
            value={"result": "skipped"},
            source_type="task",
            confidence=1,
        ),
        MemoryEntry(
            user_id=authenticated_user_id,
            goal_id=goal.id,
            memory_type="declared",
            key="task_execution",
            value={"result": "skipped"},
            source_type="user_input",
            confidence=1,
        ),
        MemoryEntry(
            user_id=authenticated_user_id,
            goal_id=goal.id,
            memory_type="observed",
            key="another_key",
            value={"result": "skipped"},
            source_type="task",
            confidence=1,
        ),
        MemoryEntry(
            user_id=authenticated_user_id,
            goal_id=None,
            memory_type="observed",
            key="task_execution",
            value={"result": "skipped"},
            source_type="task",
            confidence=1,
        ),
    ]
    db_session.add_all([*matching, *excluded])
    db_session.commit()

    memories = list_recent_task_execution_memories(
        db_session, authenticated_user_id, goal.id
    )

    assert len(memories) == RECENT_TASK_EXECUTION_MEMORY_LIMIT == 10
    assert [memory.source_id for memory in memories] == list(
        reversed(matching_source_ids[2:])
    )
    assert all(memory.user_id == authenticated_user_id for memory in memories)
    assert all(memory.goal_id == goal.id for memory in memories)
    assert all(memory.memory_type == "observed" for memory in memories)
    assert all(memory.key == "task_execution" for memory in memories)
