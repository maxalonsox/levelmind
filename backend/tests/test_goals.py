import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser, get_current_user
from app.main import app
from app.models.goal import Goal


async def post_goal(
    payload: dict[str, Any],
    access_token: str | None = None,
) -> Response:
    transport = ASGITransport(app=app)
    headers = (
        {"Authorization": f"Bearer {access_token}"}
        if access_token is not None
        else None
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/goals", json=payload, headers=headers)


def valid_goal_payload() -> dict[str, Any]:
    return {
        "title": "Become a backend developer",
        "current_situation": "I know Python fundamentals",
        "expected_outcome": "Build and deploy production APIs",
        "target_timeframe": "6 months",
        "availability": "8 hours per week",
    }


def test_create_goal_returns_authenticated_user_as_owner(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
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
    assert body["user_id"] == str(authenticated_user_id)
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
    assert persisted_goal.user_id == authenticated_user_id


def test_create_goal_rejects_second_active_goal(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    first = asyncio.run(post_goal(valid_goal_payload()))

    second = asyncio.run(post_goal(valid_goal_payload()))

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "User already has an active Goal"}
    assert len(list(db_session.scalars(select(Goal)))) == 1


def test_different_user_can_create_their_own_active_goal(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    first = asyncio.run(post_goal(valid_goal_payload()))
    other_user_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=other_user_id
    )

    second = asyncio.run(post_goal(valid_goal_payload()))

    assert first.status_code == 201
    assert second.status_code == 201
    assert {goal.user_id for goal in db_session.scalars(select(Goal))} == {
        authenticated_user_id,
        other_user_id,
    }


def test_create_goal_rejects_empty_title(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    payload = valid_goal_payload()
    payload["title"] = ""

    response = asyncio.run(post_goal(payload))

    assert response.status_code == 422
    assert db_session.scalar(select(Goal)) is None


def test_create_goal_rejects_backend_controlled_fields(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    payload = valid_goal_payload()
    payload.update(
        {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "status": "completed",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )

    response = asyncio.run(post_goal(payload))

    assert response.status_code == 422
    assert db_session.scalar(select(Goal)) is None


def test_create_goal_requires_authentication(db_session: Session) -> None:
    response = asyncio.run(post_goal(valid_goal_payload()))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert db_session.scalar(select(Goal)) is None


def test_create_goal_rejects_invalid_access_token(db_session: Session) -> None:
    response = asyncio.run(
        post_goal(valid_goal_payload(), access_token="not-a-valid-jwt")
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert db_session.scalar(select(Goal)) is None
