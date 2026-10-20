from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import DbSession
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPairResponse
from app.services.auth import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    authenticate_user,
    create_user,
    issue_token_pair,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth")


@router.post("/register", response_model=TokenPairResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: DbSession) -> TokenPairResponse:
    try:
        user = await create_user(
            session,
            email=str(payload.email),
            password=payload.password,
            display_name=payload.display_name,
        )
    except EmailAlreadyRegisteredError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册") from error
    return await issue_token_pair(session, user)


@router.post("/login", response_model=TokenPairResponse)
async def login(payload: LoginRequest, session: DbSession) -> TokenPairResponse:
    try:
        user = await authenticate_user(session, email=str(payload.email), password=payload.password)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误"
        ) from error
    return await issue_token_pair(session, user)


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(payload: RefreshRequest, session: DbSession) -> TokenPairResponse:
    try:
        return await rotate_refresh_token(session, payload.refresh_token)
    except InvalidRefreshTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌无效或已过期"
        ) from error


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, session: DbSession) -> Response:
    await revoke_refresh_token(session, payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
