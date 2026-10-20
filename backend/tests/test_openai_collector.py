import json
from pathlib import Path

import pytest

from app.collectors.openai import (
    extract_reader_markdown,
    markdown_inline_to_text,
    normalize_openai_fixture,
    normalize_openai_markdown,
    openai_markdown_to_blocks,
    split_openai_table_row,
    with_retries,
)

FIXTURES = Path(__file__).parents[1] / "app" / "collectors" / "fixtures" / "openai"


@pytest.mark.parametrize("name", ["gpt-5-6.json", "samsung.json"])
def test_openai_fixture_normalizes_rich_blocks(name: str) -> None:
    payload = json.loads((FIXTURES / name).read_text())
    article = normalize_openai_fixture(payload)
    assert article.source_key == "openai"
    assert article.published_at.tzinfo is not None
    assert article.raw_payload == payload
    assert article.content_blocks
    assert len(article.content_hash) == 64


def test_content_hash_deduplicates_identical_payload() -> None:
    payload = json.loads((FIXTURES / "gpt-5-6.json").read_text())
    assert (
        normalize_openai_fixture(payload).content_hash
        == normalize_openai_fixture(payload).content_hash
    )


def test_openai_formatter_preserves_source_order_and_words() -> None:
    markdown = """原文第一段，不应被总结或改写。

## 官方章节

* 第一项
* 第二项

![官方图片](https://images.example.com/source.png)

> 官方引用
"""
    blocks = openai_markdown_to_blocks(markdown)
    assert [block["type"] for block in blocks] == [
        "paragraph",
        "heading",
        "list",
        "image",
        "quote",
    ]
    assert blocks[0]["data"]["text"] == "原文第一段，不应被总结或改写。"
    assert blocks[2]["data"]["items"] == ["第一项", "第二项"]


def test_openai_markdown_hash_changes_with_source_content() -> None:
    payload = json.loads((FIXTURES / "gpt-5-6.json").read_text())
    first = normalize_openai_markdown(payload, "原文 A")
    second = normalize_openai_markdown(payload, "原文 B")
    assert first.content_hash != second.content_hash


def test_reader_wrapper_is_not_stored_as_article_content() -> None:
    document = "Title: 示例\n\nURL Source: https://openai.com/example\n\nMarkdown Content:\n正文"
    assert extract_reader_markdown(document) == "正文"


def test_inline_markdown_is_displayed_without_markup_but_source_is_retained() -> None:
    source = "在[官方文档](https://openai.com/docs)中使用 **Sol** 和 `ultra`。"
    assert markdown_inline_to_text(source) == "在官方文档中使用 Sol 和 ultra。"
    block = openai_markdown_to_blocks(source)[0]
    assert block["data"] == {
        "text": "在官方文档中使用 Sol 和 ultra。",
        "source_markdown": source,
    }


def test_openai_benchmark_table_is_restored_from_flat_reader_text() -> None:
    markdown = """### 专业能力

**评测****GPT‑5.6 Sol****GPT‑5.6 Terra****GPT‑5.5**
Agents' Last Exam 52.7%50.4%46.9%
GDPval-AA v2 1,747.8 Elo 1,593 Elo 1,493.7 Elo
"""
    blocks = openai_markdown_to_blocks(markdown)
    assert [block["type"] for block in blocks] == ["heading", "table"]
    table = blocks[1]["data"]
    assert table["headers"] == ["评测", "GPT‑5.6 Sol", "GPT‑5.6 Terra", "GPT‑5.5"]
    assert table["rows"][0] == ["Agents' Last Exam", "52.7%", "50.4%", "46.9%"]
    assert table["rows"][1] == ["GDPval-AA v2", "1,747.8 Elo", "1,593 Elo", "1,493.7 Elo"]


def test_table_row_split_uses_last_values_when_metric_name_has_version() -> None:
    assert split_openai_table_row("Terminal-Bench 2.1 88.8%91.9%87.4%", 3) == [
        "Terminal-Bench 2.1",
        "88.8%",
        "91.9%",
        "87.4%",
    ]


@pytest.mark.asyncio
async def test_collector_retries_transient_failure() -> None:
    attempts = 0

    async def flaky():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary")
        return "ok"

    result, retry_count = await with_retries(flaky, max_retries=2)
    assert result == "ok"
    assert retry_count == 2


@pytest.mark.asyncio
async def test_collector_stops_after_retry_budget() -> None:
    async def broken():
        raise RuntimeError("still broken")

    with pytest.raises(RuntimeError):
        await with_retries(broken, max_retries=1)
