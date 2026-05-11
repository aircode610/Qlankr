import os
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient


class InvalidToken(Exception):
    pass


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    base = os.environ["SUPABASE_URL"].rstrip("/")
    return PyJWKClient(f"{base}/auth/v1/.well-known/jwks.json")


def verify_jwt(token: str) -> UUID:
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["ES256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError as e:
        raise InvalidToken("expired") from e
    except jwt.InvalidTokenError as e:
        raise InvalidToken(str(e)) from e
    sub = payload.get("sub")
    if not sub:
        raise InvalidToken("missing sub")
    try:
        return UUID(sub)
    except ValueError as e:
        raise InvalidToken(f"sub is not a valid UUID: {sub!r}") from e


async def get_current_user(authorization: str = Header(...)) -> UUID:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return verify_jwt(token)
    except InvalidToken as e:
        raise HTTPException(status_code=401, detail=str(e))
