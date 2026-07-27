from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes import auth
from app.db.session import get_db_session
from app.main import app
from app.schemas.auth import TokenPairResponse, UserResponse
from app.services.auth import InvalidCredentialsError


async def fake_session():
    yield object()


def token_response() -> TokenPairResponse:
    return TokenPairResponse(
        access_token="access-token",
        refresh_token="r" * 64,
        expires_in=900,
        user=UserResponse(
            id=uuid4(),
            email="observer@example.com",
            display_name="Observer",
            is_active=True,
            created_at=datetime.now(UTC),
        ),
    )


def test_register_returns_token_pair(monkeypatch) -> None:
    async def create_user_stub(*_, **__):
        return object()

    async def issue_token_pair_stub(*_, **__):
        return token_response()

    app.dependency_overrides[get_db_session] = fake_session
    monkeypatch.setattr(auth, "create_user", create_user_stub)
    monkeypatch.setattr(auth, "issue_token_pair", issue_token_pair_stub)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "observer@example.com", "password": "a-strong-password"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["access_token"] == "access-token"


def test_login_rejects_invalid_credentials(monkeypatch) -> None:
    async def authenticate_stub(*_, **__):
        raise InvalidCredentialsError

    app.dependency_overrides[get_db_session] = fake_session
    monkeypatch.setattr(auth, "authenticate_user", authenticate_stub)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "observer@example.com", "password": "wrong-password"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == "邮箱或密码错误"


def test_refresh_returns_a_rotated_token_pair(monkeypatch) -> None:
    async def rotate_stub(*_, **__):
        return token_response()

    app.dependency_overrides[get_db_session] = fake_session
    monkeypatch.setattr(auth, "rotate_refresh_token", rotate_stub)
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": "r" * 64})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["refresh_token"] == "r" * 64


def test_logout_revokes_the_submitted_refresh_token(monkeypatch) -> None:
    received = []

    async def revoke_stub(_, token):
        received.append(token)

    app.dependency_overrides[get_db_session] = fake_session
    monkeypatch.setattr(auth, "revoke_refresh_token", revoke_stub)
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/logout", json={"refresh_token": "r" * 64})
    app.dependency_overrides.clear()

    assert response.status_code == 204
    assert received == ["r" * 64]
