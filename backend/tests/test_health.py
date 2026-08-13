import asyncio

from httpx import ASGITransport, AsyncClient, Response

from app.main import app


async def get_health_response() -> Response:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/health")


def test_health_check() -> None:
    response = asyncio.run(get_health_response())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
