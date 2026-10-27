import argparse
import hashlib
import json
import mimetypes
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.collectors.openai_media import extract_openai_chart_specs, extract_openai_videos
from app.core.config import settings
from app.models.content import Article
from app.services.media import get_object_storage_client


def original_asset_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def download(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "AI-Signal/0.1"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read(), response.headers.get_content_type()


def extension_for(url: str, content_type: str) -> str:
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix and len(suffix) <= 6:
        return suffix
    return mimetypes.guess_extension(content_type) or ".bin"


CHART_GROUPS = (
    (
        "openai-benchmark-overview",
        ("Agents' Last Exam", "Artificial Analysis Intelligence Index v4.1"),
        "GPT‑5.6 搭载",
    ),
    (
        "openai-coding-benchmarks",
        (
            "Artificial Analysis Coding Agent Index v1.1",
            "Terminal-Bench 2.1",
            "DeepSWE v1.1",
        ),
        "GPT‑5.6 能够编写",
    ),
    (
        "openai-multi-agent-benchmarks",
        (
            "BrowseComp (多智能体)",
            "SEC-Bench Pro (多智能体)",
            "Terminal-Bench 2.1 (多智能体)",
        ),
        "GPT‑5.6 在设计审美",
    ),
    (
        "openai-knowledge-work-benchmarks",
        ("BrowseComp", "GDPval-AA v2", "OSWorld 2.0", "AutomationBench"),
        "GPT‑5.6 Sol 提升了演示文稿",
    ),
    (
        "openai-cybersecurity-benchmarks",
        ("ExploitBench", "GeneBench Pro", "RSI Index", "ExploitGym", "SEC-Bench Pro", "夺旗挑战"),
        "GPT‑5.6 Sol 在科学研究",
    ),
    (
        "openai-science-benchmarks",
        ("LifeSciBench", "MedChemBench"),
        "GPT‑5.6 是我们目前在加速 AI 研究",
    ),
    (
        "openai-ai-research-benchmarks",
        ("内部研究调试评估", "KernelGen 1P", "NanoGPT"),
        "随着模型能力不断提升",
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror OpenAI article media into MinIO.")
    parser.add_argument("html", type=Path)
    parser.add_argument("--slug", default="gpt-5-6")
    args = parser.parse_args()

    document = args.html.read_text()
    storage = get_object_storage_client()
    engine = create_engine(settings.sync_database_url)
    with Session(engine) as session:
        article = session.scalar(
            select(Article).where(Article.canonical_url.contains(f"/{args.slug}/"))
        )
        if article is None:
            raise RuntimeError(f"article not found: {args.slug}")

        blocks = list(article.content_blocks)
        for block in blocks:
            if block["type"] != "image":
                continue
            source_url = original_asset_url(
                block["data"].get("source_url", block["data"]["url"])
            )
            body, content_type = download(source_url)
            digest = hashlib.sha256(body).hexdigest()
            extension = extension_for(source_url, content_type)
            object_key = f"openai/{args.slug}/media/{digest}{extension}"
            storage.put_object(
                Bucket=settings.s3_public_bucket,
                Key=object_key,
                Body=body,
                ContentType=content_type,
                Metadata={"source-url": source_url},
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

        video_blocks = [
            {
                "id": f"openai-video-{index:02d}",
                "type": "video_embed",
                "data": {
                    "provider": "vimeo",
                    "embed_url": video.embed_url,
                    "source_url": video.embed_url,
                    "alt": video.alt,
                },
            }
            for index, video in enumerate(extract_openai_videos(document), start=1)
        ]
        blocks = [
            block
            for block in blocks
            if block["type"] not in {"video_embed", "media_tabs", "chart_tabs"}
        ]
        if video_blocks:
            blocks.insert(0, video_blocks[0])

        demo_videos = video_blocks[1:]
        if demo_videos:
            media_tabs = {
                "id": "openai-interactive-demos",
                "type": "media_tabs",
                "data": {
                    "items": [
                        {**block["data"], "label": label}
                        for block, label in zip(
                            demo_videos,
                            [
                                "交互式万花尺",
                                "交互式波的干涉",
                                "交互式 GPT 分词器 (tokenizer) 讲解",
                            ],
                            strict=False,
                        )
                    ]
                },
            }
            insertion_index = next(
                (
                    index
                    for index, block in enumerate(blocks)
                    if block["type"] == "paragraph"
                    and block["data"].get("text", "").startswith("提示词：")
                ),
                next(
                    (index for index, block in enumerate(blocks) if block["type"] == "image"),
                    len(blocks),
                ),
            )
            blocks.insert(insertion_index, media_tabs)

        chart_specs = extract_openai_chart_specs(document)
        specs_by_title = {
            spec.get("title", {}).get("text"): spec
            for spec in chart_specs
            if isinstance(spec.get("title", {}).get("text"), str)
        }
        inserted_chart_count = 0
        for block_id, titles, anchor in CHART_GROUPS:
            items = [
                {"label": title, "spec": specs_by_title[title]}
                for title in titles
                if title in specs_by_title
            ]
            if not items:
                continue
            insertion_index = next(
                (
                    index
                    for index, block in enumerate(blocks)
                    if block["type"] == "paragraph"
                    and block["data"].get("text", "").startswith(anchor)
                ),
                len(blocks),
            )
            blocks.insert(
                insertion_index,
                {"id": block_id, "type": "chart_tabs", "data": {"items": items}},
            )
            inserted_chart_count += len(items)
        article.content_blocks = blocks
        article.content_hash = hashlib.sha256(
            json.dumps(
                {"title": article.title, "blocks": blocks}, ensure_ascii=False, sort_keys=True
            ).encode()
        ).hexdigest()
        session.commit()
        print(f"synced {sum(block['type'] == 'image' for block in blocks)} images")
        print(f"synced {len(video_blocks)} video embeds")
        print(f"synced {inserted_chart_count} interactive charts")


if __name__ == "__main__":
    main()
