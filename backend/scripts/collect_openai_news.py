"""Collect OpenAI articles from the first day of the current month by default."""

import argparse
import hashlib
import json
import mimetypes
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.collectors.openai import NormalizedArticle
from app.collectors.openai_news import (
    OpenAINewsClient,
    filter_uncollected_items,
    month_start,
    normalize_openai_news_item,
)
from app.core.config import settings
from app.models.content import Article, ArticleSource, CollectionRun, Source
from app.services.media import get_object_storage_client


def text_from(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in text_from(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in text_from(item)]
    return []


def ensure_storage_buckets(storage) -> None:
    existing = {bucket["Name"] for bucket in storage.list_buckets().get("Buckets", [])}
    for name in (settings.s3_public_bucket, settings.s3_archive_bucket):
        if name not in existing:
            storage.create_bucket(Bucket=name)


def _archive_images(blocks: list[dict], client: OpenAINewsClient, storage) -> None:
    allowed_suffixes = (".ctfassets.net", ".openai.com")
    for block in blocks:
        if block.get("type") != "image":
            continue
        source_url = block.get("data", {}).get("url", "")
        host = urlsplit(source_url).hostname or ""
        if not source_url.startswith("https://") or not any(
            host == suffix.removeprefix(".") or host.endswith(suffix) for suffix in allowed_suffixes
        ):
            block["type"] = "unsupported_embed"
            block["data"] = {
                "component": "image",
                "source_url": source_url,
                "alt": block.get("data", {}).get("alt", ""),
            }
            continue
        response = client.fetch_asset(source_url)
        body = response.content
        digest = hashlib.sha256(body).hexdigest()
        content_type = response.headers.get("content-type", "application/octet-stream").split(";")[
            0
        ]
        suffix = Path(urlsplit(source_url).path).suffix
        extension = (
            suffix
            if suffix and len(suffix) <= 8
            else mimetypes.guess_extension(content_type) or ".bin"
        )
        object_key = f"openai/{digest}{extension}"
        storage.put_object(
            Bucket=settings.s3_public_bucket,
            Key=object_key,
            Body=body,
            ContentType=content_type,
            Metadata={"source-url": source_url, "sha256": digest},
        )
        block["data"].update(
            {
                "source_url": source_url,
                "object_key": object_key,
                "url": f"{settings.api_v1_prefix}/media/{object_key}",
                "mime_type": content_type,
                "sha256": digest,
                "bytes": len(body),
            }
        )


def _save_article(session: Session, storage, normalized: NormalizedArticle, document: str) -> None:
    source = session.scalar(select(Source).where(Source.key == "openai"))
    if source is None:
        source = Source(
            key="openai",
            name="OpenAI",
            type="website",
            base_url="https://openai.com",
            is_active=True,
        )
        session.add(source)
        session.flush()
    article = session.scalar(
        select(Article).where(Article.canonical_url == normalized.canonical_url)
    )
    extracted_text = "\n".join(text_from(normalized.content_blocks))
    if article is None:
        article = Article(
            canonical_url=normalized.canonical_url,
            title=normalized.title,
            subtitle=normalized.subtitle,
            summary=normalized.summary,
            author_name=normalized.author_name,
            published_at=normalized.published_at,
            language=normalized.language,
            topics=normalized.topics,
            content_blocks=normalized.content_blocks,
            extracted_text=extracted_text,
            content_hash=normalized.content_hash,
        )
        session.add(article)
        session.flush()
    else:
        article.title = normalized.title
        article.subtitle = normalized.subtitle
        article.summary = normalized.summary
        article.author_name = normalized.author_name
        article.published_at = normalized.published_at
        article.language = normalized.language
        article.topics = normalized.topics
        article.content_blocks = normalized.content_blocks
        article.extracted_text = extracted_text
        article.content_hash = normalized.content_hash

    object_key = f"openai/{normalized.external_id}/{normalized.language}/source.html"
    storage.put_object(
        Bucket=settings.s3_archive_bucket,
        Key=object_key,
        Body=document.encode(),
        ContentType="text/html; charset=utf-8",
    )
    mapping = session.scalar(
        select(ArticleSource).where(
            ArticleSource.source_id == source.id,
            ArticleSource.external_id == normalized.external_id,
        )
    )
    if mapping is None:
        mapping = ArticleSource(
            article_id=article.id,
            source_id=source.id,
            external_id=normalized.external_id,
            source_url=normalized.canonical_url,
        )
        session.add(mapping)
    mapping.article_id = article.id
    mapping.source_url = normalized.canonical_url
    mapping.raw_payload = normalized.raw_payload
    mapping.archive_object_key = object_key
    mapping.fetched_at = datetime.now(UTC)


def collect(since: date, dry_run: bool = False, max_articles: int = 500) -> tuple[int, list[str]]:
    cookie = settings.openai_cookie.get_secret_value() if settings.openai_cookie else None
    with OpenAINewsClient(cookie=cookie) as client:
        if dry_run:
            items = client.list_articles(since)[:max_articles]
            for item in items:
                print(f"{item.published_at.date()}\t{item.title}\t{item.canonical_url}")
            return len(items), []

        storage = get_object_storage_client()
        engine = create_engine(settings.sync_database_url)
        errors: list[str] = []
        saved = 0
        with Session(engine) as session:
            source = session.scalar(select(Source).where(Source.key == "openai"))
            if source is None:
                source = Source(
                    key="openai",
                    name="OpenAI",
                    type="website",
                    base_url="https://openai.com",
                    is_active=True,
                )
                session.add(source)
                session.flush()
            run = CollectionRun(source_id=source.id, status="running")
            session.add(run)
            session.flush()
            try:
                ensure_storage_buckets(storage)
                candidates = client.list_articles(since)
                candidate_urls = {item.canonical_url for item in candidates}
                existing_urls = (
                    set(
                        session.scalars(
                            select(Article.canonical_url).where(
                                Article.canonical_url.in_(candidate_urls)
                            )
                        ).all()
                    )
                    if candidate_urls
                    else set()
                )
                items = filter_uncollected_items(candidates, existing_urls)[:max_articles]
            except Exception as error:
                run.status = "failed"
                run.finished_at = datetime.now(UTC)
                run.retry_count = client.retry_count
                run.error_summary = f"{type(error).__name__}: {error}"
                session.commit()
                engine.dispose()
                raise
            for item in items:
                try:
                    document = client.fetch_article(item)
                    normalized = normalize_openai_news_item(item, document)
                    _archive_images(normalized.content_blocks, client, storage)
                    normalized = NormalizedArticle(
                        **{
                            **normalized.__dict__,
                            "content_hash": hashlib.sha256(
                                json.dumps(
                                    {
                                        "title": normalized.title,
                                        "blocks": normalized.content_blocks,
                                    },
                                    ensure_ascii=False,
                                    sort_keys=True,
                                ).encode()
                            ).hexdigest(),
                        }
                    )
                    with session.begin_nested():
                        _save_article(session, storage, normalized, document)
                    saved += 1
                except Exception as error:
                    errors.append(f"{item.external_id}: {type(error).__name__}: {error}")
            run.status = "succeeded" if not errors else "partial_failure" if saved else "failed"
            run.finished_at = datetime.now(UTC)
            run.retry_count = client.retry_count
            run.error_summary = "\n".join(errors[:20]) or None
            session.commit()
        engine.dispose()
        return saved, errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect OpenAI news since a date (defaults to month start)."
    )
    parser.add_argument("--since", type=date.fromisoformat, default=month_start())
    parser.add_argument("--max-articles", type=int, default=500)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matching articles without fetching article pages.",
    )
    args = parser.parse_args()
    try:
        count, errors = collect(args.since, args.dry_run, args.max_articles)
    except Exception as error:
        print(f"OpenAI collection failed: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    result_label = "listed" if args.dry_run else "saved"
    print(f"OpenAI collection since {args.since}: {count} {result_label}; {len(errors)} failed")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
