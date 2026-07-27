from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.schemas.auth import TokenPairResponse, UserResponse


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == normalize_email(email)))


async def create_user(
    session: AsyncSession, *, email: str, password: str, display_name: str | None
) -> User:
    user = User(
        email=normalize_email(email),
        password_hash=hash_password(password),
        display_name=display_name.strip() if display_name else None,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise EmailAlreadyRegisteredError from error
    await session.refresh(user)
    return user


async def issue_token_pair(session: AsyncSession, user: User) -> TokenPairResponse:
    access_token, expires_in = create_access_token(user.id)
    refresh_token = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    await session.commit()
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


async def authenticate_user(session: AsyncSession, *, email: str, password: str) -> User:
    user = await get_user_by_email(session, email)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    return user


async def rotate_refresh_token(session: AsyncSession, token: str) -> TokenPairResponse:
    stored_token = await session.scalar(
        select(RefreshToken)
        .options(selectinload(RefreshToken.user))
        .where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if (
        stored_token is None
        or stored_token.revoked_at is not None
        or stored_token.expires_at <= datetime.now(UTC)
        or not stored_token.user.is_active
    ):
        raise InvalidRefreshTokenError

    stored_token.revoked_at = datetime.now(UTC)
    response = await issue_token_pair(session, stored_token.user)
    return response


async def revoke_refresh_token(session: AsyncSession, token: str) -> None:
    stored_token = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if stored_token is not None and stored_token.revoked_at is None:
        stored_token.revoked_at = datetime.now(UTC)
        await session.commit()
