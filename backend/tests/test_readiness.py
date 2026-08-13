import asyncio

from httpx import ASGITransport, AsyncClient, Response

from app.api import readiness
from app.db.check import DatabaseConnectionError
from app.main import app


async def get_readiness_response() -> Response:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/ready")


def test_readiness_check_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(readiness, "check_database_connection", lambda: None)

    response = asyncio.run(get_readiness_response())

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_check_fails(monkeypatch) -> None:
    def raise_database_error() -> None:
        raise DatabaseConnectionError("Database is unavailable")

    monkeypatch.setattr(readiness, "check_database_connection", raise_database_error)

    response = asyncio.run(get_readiness_response())

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
