from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.content import ArticleDetail, ArticleListItem, ArticlePage
from app.services.content import get_article, list_articles

router = APIRouter(prefix="/articles")


@router.get("", response_model=ArticlePage)
async def articles_index(
    session: DbSession,
    _: CurrentUser,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    category: str | None = Query(default=None, min_length=1, max_length=40),
) -> ArticlePage:
    try:
        items, next_cursor = await list_articles(session, limit, cursor, category)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="分页游标无效"
        ) from error
    return ArticlePage(
        items=[ArticleListItem.model_validate(item) for item in items], next_cursor=next_cursor
    )


@router.get("/{article_id}", response_model=ArticleDetail)
async def article_detail(article_id: UUID, session: DbSession, _: CurrentUser) -> ArticleDetail:
    article = await get_article(session, article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    return ArticleDetail.model_validate(article)
