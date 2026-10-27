import json
from datetime import date
from pathlib import Path

from app.collectors.openai_news import (
    html_article_to_blocks,
    month_start,
    parse_articles_api_payload,
    parse_openai_rss,
)

FIXTURES = Path(__file__).parents[1] / "app" / "collectors" / "fixtures" / "openai"


def test_articles_api_fixture_filters_before_cutoff_and_non_articles() -> None:
    payload = json.loads((FIXTURES / "news-list.json").read_text())
    items = parse_articles_api_payload(payload, date(2026, 10, 1))

    assert len(items) == 1
    assert items[0].external_id == "5euiEKnIjReDewL2VZQyWG"
    assert items[0].canonical_url.endswith(
        "/zh-Hans-CN/index/building-scientific-understanding-with-academic-communities/"
    )
    assert items[0].topics == ["研究", "刊发"]
    assert items[0].summary == "OpenAI 分享研究成果及合作方式。"


def test_openai_rss_uses_month_cutoff_and_maps_official_categories() -> None:
    rss = """<rss><channel>
      <item><title>October story</title><link>https://openai.com/index/october-story</link>
        <pubDate>Mon, 26 Oct 2026 14:30:00 GMT</pubDate><category>Research</category>
        <description>A source supplied description</description></item>
      <item><title>September story</title><link>https://openai.com/index/september-story</link>
        <pubDate>Wed, 30 Sep 2026 14:30:00 GMT</pubDate></item>
    </channel></rss>"""

    items = parse_openai_rss(rss, date(2026, 10, 1))

    assert [item.title for item in items] == ["October story"]
    assert items[0].topics == ["研究"]
    assert items[0].summary == "A source supplied description"
    assert items[0].published_at.isoformat() == "2026-10-26T14:30:00+00:00"
    assert items[0].canonical_url == "https://openai.com/zh-Hans-CN/index/october-story/"


def test_article_html_becomes_ordered_blocks_without_table_of_contents() -> None:
    document = (FIXTURES / "article.html").read_text()
    blocks = html_article_to_blocks(
        document, "https://openai.com/index/building-scientific-understanding/"
    )

    assert [block["type"] for block in blocks] == [
        "paragraph",
        "list",
        "heading",
        "quote",
        "image",
        "video_embed",
        "source_link",
    ]
    assert blocks[0]["data"]["text"] == ("We are sharing research updates with the community.")
    assert blocks[0]["data"]["links"] == [
        {"text": "research updates", "url": "https://openai.com/research/"}
    ]
    assert blocks[1]["data"] == {
        "items": ["First release strategy", "Second release strategy"],
        "ordered": False,
    }
    assert blocks[4]["data"]["url"] == "https://images.ctfassets.net/example/image.webp"


def test_month_start_uses_explicit_date() -> None:
    assert month_start(date(2026, 10, 27)) == date(2026, 10, 1)


def test_article_chart_specs_keep_source_order_and_language_tabs() -> None:
    document = """<html><main><h1>Benchmark</h1>
      <p>Results.</p>
      <figure><figcaption>平均测试通过率</figcaption></figure>
      <figure><figcaption>SQLite 测试通过率</figcaption></figure>
    </main></html>"""
    specs = [
        {"title": "平均测试通过率", "data": {"values": [{"score": 1}]}},
        {"title": "SQLite 测试通过率 — C", "data": {"values": [{"score": 2}]}},
        {"title": "SQLite 测试通过率 — Python", "data": {"values": [{"score": 3}]}},
    ]

    blocks = html_article_to_blocks(document, "https://openai.com/index/benchmark/", specs)

    chart_blocks = [block for block in blocks if block["type"] == "chart_tabs"]
    assert len(chart_blocks) == 2
    assert [item["label"] for item in chart_blocks[0]["data"]["items"]] == ["平均测试通过率"]
    assert [item["label"] for item in chart_blocks[1]["data"]["items"]] == ["C", "Python"]
    assert not [block for block in blocks if block["type"] == "unsupported_embed"]
