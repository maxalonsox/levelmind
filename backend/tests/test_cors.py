import asyncio

import pytest
from httpx import ASGITransport, AsyncClient, Response
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app


async def preflight(origin: str) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.options(
            "/goals",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )


def test_cors_allows_configured_frontend_origin() -> None:
    response = asyncio.run(preflight("http://localhost:5173"))

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_cors_rejects_unconfigured_origin() -> None:
    response = asyncio.run(preflight("https://untrusted.example"))

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_accepts_comma_separated_origins_configuration() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@localhost/levelmind",
        supabase_url="https://test.supabase.co",
        cors_allowed_origins=(
            "http://localhost:5173, https://frontend.example.com/"
        ),
    )

    assert settings.cors_origins == [
        "http://localhost:5173",
        "https://frontend.example.com",
    ]


def test_cors_rejects_wildcard_configuration() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test:test@localhost/levelmind",
            supabase_url="https://test.supabase.co",
            cors_allowed_origins="*",
        )
