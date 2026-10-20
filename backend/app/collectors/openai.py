import asyncio
import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class NormalizedArticle:
    external_id: str
    source_key: str
    canonical_url: str
    title: str
    subtitle: str | None
    summary: str | None
    author_name: str | None
    published_at: datetime
    language: str
    topics: list[str]
    content_blocks: list[dict[str, Any]]
    metrics: dict[str, int]
    raw_payload: dict[str, Any]
    content_hash: str


OPENAI_CATEGORIES = [
    "公司",
    "研究",
    "产品",
    "安全",
    "工程",
    "安全防护",
    "全球事务",
    "AI 采用",
    "应用 AI",
]

IMAGE_PATTERN = re.compile(r"^!\[(?P<alt>.*?)]\((?P<url>https?://[^ )]+)(?:\s+\".*?\")?\)$")
HEADING_PATTERN = re.compile(r"^(?P<level>#{1,6})\s+(?P<text>.+)$")
LIST_PATTERN = re.compile(r"^\s*[-*]\s+(?P<text>.+)$")
ORDERED_LIST_PATTERN = re.compile(r"^\s*\d+[.)]\s+(?P<text>.+)$")
INLINE_LINK_PATTERN = re.compile(r"\[(?P<label>[^]]+)]\([^)]+\)")
TABLE_HEADER_PATTERN = re.compile(r"\*\*(?P<label>.*?)\*\*")
TABLE_VALUE_PATTERN = re.compile(r"—|\d[\d,]*(?:\.\d+)?(?:%|\s+Elo|\s+Index\s+得分)?")


def _block_id(index: int, block_type: str) -> str:
    return f"openai-{index:04d}-{block_type}"


def markdown_inline_to_text(value: str) -> str:
    text = INLINE_LINK_PATTERN.sub(lambda match: match["label"], value)
    for marker in ("**", "__", "`", "_"):
        text = text.replace(marker, "")
    return text.replace("⁠", "").strip()


def split_openai_table_row(line: str, value_count: int) -> list[str]:
    matches = list(TABLE_VALUE_PATTERN.finditer(line))
    if len(matches) < value_count:
        return [markdown_inline_to_text(line)]
    values = matches[-value_count:]
    label = line[: values[0].start()].strip()
    return [markdown_inline_to_text(label), *[match.group().strip() for match in values]]


def openai_markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    """Convert reader Markdown to ordered blocks without summarising or rewriting it."""
    lines = markdown.replace("\r\n", "\n").splitlines()
    blocks: list[dict[str, Any]] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_ordered = False
    table_headers: list[str] = []
    table_rows: list[list[str]] = []

    def append(block_type: str, data: dict[str, Any]) -> None:
        blocks.append(
            {"id": _block_id(len(blocks) + 1, block_type), "type": block_type, "data": data}
        )

    def flush_paragraph() -> None:
        if paragraph:
            source = "\n".join(paragraph).strip()
            append(
                "paragraph", {"text": markdown_inline_to_text(source), "source_markdown": source}
            )
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_ordered
        if list_items:
            append("list", {"items": list_items.copy(), "ordered": list_ordered})
            list_items.clear()
            list_ordered = False

    def flush_table() -> None:
        if table_headers:
            append("table", {"headers": table_headers.copy(), "rows": table_rows.copy()})
            table_headers.clear()
            table_rows.clear()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_list()
            flush_table()
            continue
        heading = HEADING_PATTERN.match(line)
        image = IMAGE_PATTERN.match(line)
        unordered_item = LIST_PATTERN.match(line)
        ordered_item = ORDERED_LIST_PATTERN.match(line)
        header_labels = [match["label"] for match in TABLE_HEADER_PATTERN.finditer(line)]
        if header_labels and header_labels[0] == "评测":
            flush_paragraph()
            flush_list()
            flush_table()
            table_headers.extend(header_labels)
        elif table_headers:
            table_rows.append(split_openai_table_row(line, len(table_headers) - 1))
        elif heading:
            flush_paragraph()
            flush_list()
            flush_table()
            append(
                "heading",
                {
                    "level": len(heading["level"]),
                    "text": markdown_inline_to_text(heading["text"]),
                },
            )
        elif image:
            flush_paragraph()
            flush_list()
            append("image", {"url": image["url"], "alt": image["alt"]})
        elif unordered_item or ordered_item:
            flush_paragraph()
            item = unordered_item or ordered_item
            if list_items and list_ordered != bool(ordered_item):
                flush_list()
            list_ordered = bool(ordered_item)
            list_items.append(markdown_inline_to_text(item["text"]))
        elif line.startswith(">"):
            flush_paragraph()
            flush_list()
            append(
                "quote",
                {
                    "text": markdown_inline_to_text(line.removeprefix(">").strip()),
                    "attribution": None,
                },
            )
        elif line.startswith("|") and line.endswith("|"):
            flush_paragraph()
            flush_list()
            append("table_row", {"cells": [cell.strip() for cell in line.strip("|").split("|")]})
        else:
            flush_list()
            paragraph.append(line)
    flush_paragraph()
    flush_list()
    flush_table()
    return blocks


def extract_reader_markdown(document: str) -> str:
    marker = "Markdown Content:"
    if marker not in document:
        return document.strip()
    return document.split(marker, 1)[1].strip()


def normalize_openai_markdown(payload: dict[str, Any], markdown: str) -> NormalizedArticle:
    source_markdown = extract_reader_markdown(markdown)
    blocks = openai_markdown_to_blocks(source_markdown)
    blocks.append(
        {
            "id": _block_id(len(blocks) + 1, "source_link"),
            "type": "source_link",
            "data": {"label": "在 OpenAI 阅读原文", "url": payload["canonicalUrl"]},
        }
    )
    normalized_payload = {**payload, "blocks": blocks}
    normalized_payload["rawMarkdown"] = source_markdown
    return normalize_openai_fixture(normalized_payload)


def normalize_openai_fixture(payload: dict[str, Any]) -> NormalizedArticle:
    required = {"externalId", "canonicalUrl", "title", "publishedAt", "blocks"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"missing OpenAI fields: {', '.join(sorted(missing))}")
    published_at = datetime.fromisoformat(payload["publishedAt"].replace("Z", "+00:00"))
    hash_input = json.dumps(
        {"title": payload["title"], "blocks": payload["blocks"]}, ensure_ascii=False, sort_keys=True
    )
    content_hash = hashlib.sha256(hash_input.encode()).hexdigest()
    return NormalizedArticle(
        external_id=payload["externalId"],
        source_key="openai",
        canonical_url=payload["canonicalUrl"],
        title=payload["title"],
        subtitle=payload.get("subtitle"),
        summary=payload.get("summary"),
        author_name=payload.get("authorName", "OpenAI"),
        published_at=published_at,
        language=payload.get("language", "zh-Hans-CN"),
        topics=payload.get("topics", []),
        content_blocks=payload["blocks"],
        metrics=payload.get("metrics", {}),
        raw_payload=payload,
        content_hash=content_hash,
    )


def load_fixtures(directory: Path) -> list[NormalizedArticle]:
    return [
        normalize_openai_fixture(json.loads(path.read_text()))
        for path in sorted(directory.glob("*.json"))
    ]


async def with_retries(
    operation: Callable[[], Awaitable[Any]], max_retries: int = 2
) -> tuple[Any, int]:
    retry_count = 0
    while True:
        try:
            return await operation(), retry_count
        except Exception:
            if retry_count >= max_retries:
                raise
            retry_count += 1
            await asyncio.sleep(0)
