from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContentBlock(BaseModel):
    type: str
    id: str
    data: dict[str, Any] = Field(default_factory=dict)


class ArticleListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    subtitle: str | None
    summary: str | None
    author_name: str | None
    published_at: datetime
    language: str
    topics: list[str]
    canonical_url: str


class ArticleDetail(ArticleListItem):
    content_blocks: list[ContentBlock]


class ArticlePage(BaseModel):
    items: list[ArticleListItem]
    next_cursor: str | None = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    key: str
    name: str
    type: str
    base_url: str
    is_active: bool
