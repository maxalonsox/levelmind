from functools import lru_cache
from typing import Annotated, Any
from urllib.error import URLError
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWTError
from pydantic import BaseModel

from app.core.config import get_settings

ALLOWED_JWT_ALGORITHMS = ("ES256",)
SUPABASE_JWT_AUDIENCE = "authenticated"

bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    id: UUID


class InvalidAccessTokenError(Exception):
    pass


@lru_cache
def get_jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, lifespan=600, timeout=5)


def verify_access_token(token: str) -> AuthenticatedUser:
    settings = get_settings()
    issuer = f"{str(settings.supabase_url).rstrip('/')}/auth/v1"
    jwks_client = get_jwks_client(f"{issuer}/.well-known/jwks.json")

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=ALLOWED_JWT_ALGORITHMS,
            audience=SUPABASE_JWT_AUDIENCE,
            issuer=issuer,
            options={"require": ["aud", "exp", "iss", "sub"]},
        )
        user_id = UUID(str(claims["sub"]))
    except (KeyError, PyJWTError, TimeoutError, URLError, ValueError):
        raise InvalidAccessTokenError from None

    return AuthenticatedUser(id=user_id)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedUser:
    if credentials is None:
        raise _unauthorized_error()

    try:
        return verify_access_token(credentials.credentials)
    except InvalidAccessTokenError:
        raise _unauthorized_error() from None


def _unauthorized_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
