import base64
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Article, Source


def encode_cursor(published_at: datetime, article_id: UUID) -> str:
    return base64.urlsafe_b64encode(f"{published_at.isoformat()}|{article_id}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        value = base64.urlsafe_b64decode(cursor.encode()).decode()
        timestamp, article_id = value.rsplit("|", 1)
        return datetime.fromisoformat(timestamp), UUID(article_id)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("invalid cursor") from error


async def list_articles(
    session: AsyncSession,
    limit: int,
    cursor: str | None = None,
    category: str | None = None,
) -> tuple[list[Article], str | None]:
    statement = (
        select(Article)
        .where(Article.language.like("zh%"))
        .where(Article.title.op("~")("[\u3400-\u4dbf\u4e00-\u9fff]"))
        .order_by(Article.published_at.desc(), Article.id.desc())
        .limit(limit + 1)
    )
    if category:
        statement = statement.where(Article.topics.contains([category]))
    if cursor:
        published_at, article_id = decode_cursor(cursor)
        statement = statement.where(
            or_(
                Article.published_at < published_at,
                and_(Article.published_at == published_at, Article.id < article_id),
            )
        )
    items = list((await session.scalars(statement)).all())
    has_more = len(items) > limit
    items = items[:limit]
    next_cursor = encode_cursor(items[-1].published_at, items[-1].id) if has_more else None
    return items, next_cursor


async def get_article(session: AsyncSession, article_id: UUID) -> Article | None:
    statement = (
        select(Article).options(selectinload(Article.sources)).where(Article.id == article_id)
    )
    return await session.scalar(statement)


async def list_sources(session: AsyncSession) -> list[Source]:
    return list((await session.scalars(select(Source).order_by(Source.name))).all())
