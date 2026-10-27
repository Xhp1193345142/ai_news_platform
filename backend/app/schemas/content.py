from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @field_validator("subtitle", "summary", mode="before")
    @classmethod
    def omit_non_chinese_descriptions(cls, value: str | None) -> str | None:
        if value is not None and not any("\u3400" <= char <= "\u9fff" for char in value):
            return None
        return value


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
