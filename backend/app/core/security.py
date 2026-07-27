import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user_id: UUID) -> tuple[str, int]:
    expires_in = settings.access_token_expire_minutes * 60
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    payload = {"sub": str(user_id), "type": "access", "exp": expires_at, "iat": datetime.now(UTC)}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm), expires_in


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as error:
        raise ValueError("无效或已过期的访问令牌") from error

    if payload.get("type") != "access" or not payload.get("sub"):
        raise ValueError("无效的访问令牌")
    try:
        return UUID(payload["sub"])
    except (TypeError, ValueError) as error:
        raise ValueError("无效的访问令牌") from error


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
