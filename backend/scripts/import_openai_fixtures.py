import json
from datetime import UTC, datetime
from pathlib import Path

import boto3
from botocore.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.collectors.openai import NormalizedArticle, load_fixtures
from app.core.config import settings
from app.models.content import Article, ArticleSource, CollectionRun, Source

FIXTURE_DIR = Path(__file__).parents[1] / "app" / "collectors" / "fixtures" / "openai"


def text_from(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in text_from(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in text_from(item)]
    return []


def ensure_buckets():
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(s3={"addressing_style": "path"}),
    )
    existing = {bucket["Name"] for bucket in client.list_buckets().get("Buckets", [])}
    for bucket in (settings.s3_public_bucket, settings.s3_archive_bucket):
        if bucket not in existing:
            client.create_bucket(Bucket=bucket)
    return client


def import_articles(articles: list[NormalizedArticle]) -> None:
    storage = ensure_buckets()
    engine = create_engine(settings.sync_database_url)
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
            for normalized in articles:
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
                    article.topics = normalized.topics
                    article.content_blocks = normalized.content_blocks
                    article.extracted_text = extracted_text
                    article.content_hash = normalized.content_hash
                object_key = f"openai/{normalized.external_id}/{normalized.language}/source.json"
                storage.put_object(
                    Bucket=settings.s3_archive_bucket,
                    Key=object_key,
                    Body=json.dumps(normalized.raw_payload, ensure_ascii=False).encode(),
                    ContentType="application/json",
                )
                mapping = session.scalar(
                    select(ArticleSource).where(
                        ArticleSource.source_id == source.id,
                        ArticleSource.external_id == normalized.external_id,
                    )
                )
                if mapping is None:
                    session.add(
                        ArticleSource(
                            article_id=article.id,
                            source_id=source.id,
                            external_id=normalized.external_id,
                            source_url=normalized.canonical_url,
                            raw_payload=normalized.raw_payload,
                            metrics=normalized.metrics,
                            archive_object_key=object_key,
                        )
                    )
                else:
                    mapping.article_id = article.id
                    mapping.raw_payload = normalized.raw_payload
                    mapping.archive_object_key = object_key
                    mapping.fetched_at = datetime.now(UTC)
            run.status = "succeeded"
            run.finished_at = datetime.now(UTC)
            session.commit()
        except Exception as error:
            session.rollback()
            raise RuntimeError(f"OpenAI fixture import failed: {error}") from error


def main() -> None:
    import_articles(load_fixtures(FIXTURE_DIR))


if __name__ == "__main__":
    main()
