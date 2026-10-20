from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.routes import articles
from app.db.session import get_db_session
from app.main import app


async def fake_session():
    yield object()


async def fake_user():
    return object()


def sample_article():
    return SimpleNamespace(
        id=uuid4(),
        title="GPT‑5.6",
        subtitle="前沿智能",
        summary="摘要",
        author_name="OpenAI",
        published_at=datetime.now(UTC),
        language="zh-Hans-CN",
        topics=["模型"],
        canonical_url="https://openai.com/example",
        content_blocks=[{"id": "intro", "type": "paragraph", "data": {"text": "正文"}}],
    )


def test_articles_require_authentication() -> None:
    app.dependency_overrides[get_db_session] = fake_session
    with TestClient(app) as client:
        response = client.get("/api/v1/articles")
    app.dependency_overrides.clear()
    assert response.status_code == 401


def test_articles_list_contract(monkeypatch) -> None:
    received = {}

    async def list_stub(_session, limit, cursor, category):
        received.update(limit=limit, cursor=cursor, category=category)
        return [sample_article()], None

    app.dependency_overrides[get_db_session] = fake_session
    app.dependency_overrides[get_current_user] = fake_user
    monkeypatch.setattr(articles, "list_articles", list_stub)
    with TestClient(app) as client:
        response = client.get("/api/v1/articles?category=产品")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "GPT‑5.6"
    assert received == {"limit": 20, "cursor": None, "category": "产品"}


def test_article_not_found(monkeypatch) -> None:
    async def get_stub(*_):
        return None

    app.dependency_overrides[get_db_session] = fake_session
    app.dependency_overrides[get_current_user] = fake_user
    monkeypatch.setattr(articles, "get_article", get_stub)
    with TestClient(app) as client:
        response = client.get(f"/api/v1/articles/{uuid4()}")
    app.dependency_overrides.clear()
    assert response.status_code == 404
