import time
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

import auth


@pytest.fixture(autouse=True)
def supabase_url(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")


@pytest.fixture
def keypair():
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    return priv, pub


@pytest.fixture
def stub_jwks(monkeypatch, keypair):
    _, pub = keypair

    class _StubKey:
        @property
        def key(self):
            return pub

    class _StubClient:
        def get_signing_key_from_jwt(self, token):
            return _StubKey()

    auth._jwks_client.cache_clear()
    monkeypatch.setattr(auth, "_jwks_client", lambda: _StubClient())


def _make_token(priv_key, payload):
    return jwt.encode(payload, priv_key, algorithm="ES256")


def test_verify_jwt_returns_user_id_for_valid_token(stub_jwks, keypair):
    priv, _ = keypair
    uid = uuid4()
    token = _make_token(priv, {
        "sub": str(uid),
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
    })
    assert auth.verify_jwt(token) == uid


def test_verify_jwt_rejects_expired_token(stub_jwks, keypair):
    priv, _ = keypair
    token = _make_token(priv, {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "exp": int(time.time()) - 1,
    })
    with pytest.raises(auth.InvalidToken, match="expired"):
        auth.verify_jwt(token)


def test_verify_jwt_rejects_wrong_audience(stub_jwks, keypair):
    priv, _ = keypair
    token = _make_token(priv, {
        "sub": str(uuid4()),
        "aud": "service_role",
        "exp": int(time.time()) + 3600,
    })
    with pytest.raises(auth.InvalidToken):
        auth.verify_jwt(token)


def test_verify_jwt_rejects_bad_signature(stub_jwks):
    other_priv = ec.generate_private_key(ec.SECP256R1())
    payload = {"sub": str(uuid4()), "aud": "authenticated", "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, other_priv, algorithm="ES256")
    with pytest.raises(auth.InvalidToken):
        auth.verify_jwt(token)


from fastapi import HTTPException


@pytest.mark.asyncio
async def test_get_current_user_returns_uuid_for_valid_bearer(stub_jwks, keypair):
    priv, _ = keypair
    uid = uuid4()
    token = _make_token(priv, {
        "sub": str(uid),
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
    })
    result = await auth.get_current_user(authorization=f"Bearer {token}")
    assert result == uid


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_bearer_prefix(stub_jwks):
    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(authorization="not-a-bearer-token")
    assert exc_info.value.status_code == 401
    assert "missing bearer token" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token(stub_jwks):
    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(authorization="Bearer not-a-real-jwt")
    assert exc_info.value.status_code == 401
