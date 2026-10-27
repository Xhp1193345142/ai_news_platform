from types import SimpleNamespace

import pytest

from app.schemas.content import ArticleListItem
from app.services.content import list_articles


class CapturingSession:
    statement = None

    async def scalars(self, statement):
        self.statement = statement
        return SimpleNamespace(all=lambda: [])


@pytest.mark.asyncio
async def test_article_feed_only_returns_chinese_language_articles() -> None:
    session = CapturingSession()

    items, next_cursor = await list_articles(session, limit=20)

    assert items == []
    assert next_cursor is None
    assert "articles.language LIKE" in str(session.statement)
    assert "articles.title ~" in str(session.statement)
    assert {"zh%", "[\u3400-\u4dbf\u4e00-\u9fff]"}.issubset(
        session.statement.compile().params.values()
    )


def test_article_response_hides_english_descriptions() -> None:
    article = ArticleListItem(
        id="91a58ab0-85cd-4f57-a4a6-244b4d780fbf",
        title="中文标题",
        subtitle="An English subtitle",
        summary="English only summary",
        author_name="OpenAI",
        published_at="2026-10-26T00:00:00Z",
        language="zh-Hans-CN",
        topics=["产品"],
        canonical_url="https://openai.com/zh-Hans-CN/index/example/",
    )

    assert article.subtitle is None
    assert article.summary is None
