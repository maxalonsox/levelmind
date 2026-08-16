import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.goal import Goal


@pytest.fixture
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        yield session

    engine.dispose()


@pytest.fixture(autouse=True)
def override_database_dependency(db_session: Session):
    def get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)


async def post_goal(payload: dict[str, Any]) -> Response:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/goals", json=payload)


def valid_goal_payload() -> dict[str, Any]:
    return {
        "user_id": str(uuid4()),
        "title": "Become a backend developer",
        "current_situation": "I know Python fundamentals",
        "expected_outcome": "Build and deploy production APIs",
        "target_timeframe": "6 months",
        "availability": "8 hours per week",
    }


def test_create_goal_returns_201_and_response_contract(db_session: Session) -> None:
    payload = valid_goal_payload()

    response = asyncio.run(post_goal(payload))

    assert response.status_code == 201

    body = response.json()
    assert set(body) == {
        "id",
        "user_id",
        "title",
        "current_situation",
        "expected_outcome",
        "target_timeframe",
        "availability",
        "status",
        "created_at",
        "updated_at",
    }
    assert UUID(body["id"])
    assert body["user_id"] == payload["user_id"]
    assert body["title"] == payload["title"]
    assert body["current_situation"] == payload["current_situation"]
    assert body["expected_outcome"] == payload["expected_outcome"]
    assert body["target_timeframe"] == payload["target_timeframe"]
    assert body["availability"] == payload["availability"]
    assert body["status"] == "active"
    assert datetime.fromisoformat(body["created_at"])
    assert datetime.fromisoformat(body["updated_at"])

    persisted_goal = db_session.scalar(select(Goal))
    assert persisted_goal is not None
    assert str(persisted_goal.id) == body["id"]


def test_create_goal_rejects_empty_title(db_session: Session) -> None:
    payload = valid_goal_payload()
    payload["title"] = ""

    response = asyncio.run(post_goal(payload))

    assert response.status_code == 422
    assert db_session.scalar(select(Goal)) is None


def test_create_goal_rejects_backend_controlled_fields(db_session: Session) -> None:
    payload = valid_goal_payload()
    payload.update(
        {
            "id": str(uuid4()),
            "status": "completed",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )

    response = asyncio.run(post_goal(payload))

    assert response.status_code == 422
    assert db_session.scalar(select(Goal)) is None
