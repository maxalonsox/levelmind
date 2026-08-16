from uuid import uuid4

import jwt
import pytest

from app import auth


class StubSigningKey:
    key = object()


class StubJwksClient:
    def get_signing_key_from_jwt(self, token: str) -> StubSigningKey:
        assert token == "access-token"
        return StubSigningKey()


def test_verify_access_token_validates_supabase_claims(monkeypatch) -> None:
    user_id = uuid4()
    decode_arguments = {}

    monkeypatch.setattr(auth, "get_jwks_client", lambda url: StubJwksClient())

    def decode_token(token, key, **kwargs):
        decode_arguments.update(kwargs)
        return {
            "aud": "authenticated",
            "exp": 2_000_000_000,
            "iss": "https://test.supabase.co/auth/v1",
            "sub": str(user_id),
        }

    monkeypatch.setattr(auth.jwt, "decode", decode_token)

    current_user = auth.verify_access_token("access-token")

    assert current_user.id == user_id
    assert decode_arguments == {
        "algorithms": ("ES256",),
        "audience": "authenticated",
        "issuer": "https://test.supabase.co/auth/v1",
        "options": {"require": ["aud", "exp", "iss", "sub"]},
    }


def test_verify_access_token_rejects_invalid_token(monkeypatch) -> None:
    monkeypatch.setattr(auth, "get_jwks_client", lambda url: StubJwksClient())
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            jwt.ExpiredSignatureError
        ),
    )

    with pytest.raises(auth.InvalidAccessTokenError):
        auth.verify_access_token("access-token")


def test_verify_access_token_rejects_non_uuid_subject(monkeypatch) -> None:
    monkeypatch.setattr(auth, "get_jwks_client", lambda url: StubJwksClient())
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *args, **kwargs: {
            "aud": "authenticated",
            "exp": 2_000_000_000,
            "iss": "https://test.supabase.co/auth/v1",
            "sub": "not-a-uuid",
        },
    )

    with pytest.raises(auth.InvalidAccessTokenError):
        auth.verify_access_token("access-token")
