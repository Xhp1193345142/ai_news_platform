import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.collectors.openai_news import (
    OPENAI_ARTICLES_API,
    OPENAI_RSS_URL,
    OpenAINewsClient,
    filter_uncollected_items,
    html_article_to_blocks,
    month_start,
    normalize_openai_news_item,
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


def test_collector_deduplicates_canonical_urls_before_fetch_and_skips_stored_urls() -> None:
    candidates = parse_openai_rss(
        """<rss><channel>
          <item><title>First duplicate</title><link>https://openai.com/index/duplicate</link>
            <pubDate>Mon, 26 Oct 2026 14:30:00 GMT</pubDate></item>
          <item><title>Second duplicate</title><link>https://openai.com/zh-Hans-CN/index/duplicate/</link>
            <pubDate>Mon, 26 Oct 2026 14:30:00 GMT</pubDate></item>
          <item><title>Already stored</title><link>https://openai.com/index/stored</link>
            <pubDate>Mon, 26 Oct 2026 14:30:00 GMT</pubDate></item>
          <item><title>New</title><link>https://openai.com/index/new</link>
            <pubDate>Mon, 26 Oct 2026 14:30:00 GMT</pubDate></item>
        </channel></rss>""",
        date(2026, 10, 1),
    )

    ready = filter_uncollected_items(
        candidates,
        {"https://openai.com/zh-Hans-CN/index/stored/"},
    )

    assert [item.canonical_url for item in ready] == [
        "https://openai.com/zh-Hans-CN/index/duplicate/",
        "https://openai.com/zh-Hans-CN/index/new/",
    ]
    assert ready[0].title == "First duplicate"


def test_client_merges_api_and_rss_so_partial_api_results_do_not_hide_articles() -> None:
    payload = json.loads((FIXTURES / "news-list.json").read_text())
    rss = """<rss><channel>
      <item><title>API duplicate</title>
        <link>https://openai.com/index/building-scientific-understanding-with-academic-communities</link>
        <pubDate>Mon, 26 Oct 2026 14:30:00 GMT</pubDate></item>
      <item><title>RSS-only story</title><link>https://openai.com/index/rss-only-story</link>
        <pubDate>Fri, 23 Oct 2026 14:30:00 GMT</pubDate></item>
    </channel></rss>"""

    def respond(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(OPENAI_ARTICLES_API):
            return httpx.Response(200, json=payload)
        if str(request.url) == OPENAI_RSS_URL:
            return httpx.Response(200, text=rss)
        raise AssertionError(f"unexpected request: {request.url}")

    http_client = httpx.Client(transport=httpx.MockTransport(respond))
    client = OpenAINewsClient(client=http_client, cookie="session-cookie")
    try:
        items = client.list_articles(date(2026, 10, 1))
    finally:
        http_client.close()

    assert len(items) == 2
    assert items[0].title == "携手学术界，深化科学认识"
    assert items[1].title == "RSS-only story"


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
    assert blocks[0]["data"]["text"] == "我们分享了与社区共同开展的研究进展。"
    assert blocks[0]["data"]["links"] == [
        {"text": "研究进展", "url": "https://openai.com/research/"}
    ]
    assert blocks[1]["data"] == {
        "items": ["第一项发布策略", "第二项发布策略"],
        "ordered": False,
    }
    assert blocks[4]["data"]["url"] == "https://images.ctfassets.net/example/image.webp"


def test_normalizer_uses_chinese_page_title_summary_and_body() -> None:
    payload = json.loads((FIXTURES / "news-list.json").read_text())
    item = parse_articles_api_payload(payload, date(2026, 10, 1))[0]
    document = (FIXTURES / "article.html").read_text()

    article = normalize_openai_news_item(item, document)

    assert article.title == "携手学术界，深化科学认识"
    assert article.language == "zh-Hans-CN"
    assert article.summary == "与学术界合作，推动科学理解。"
    assert article.content_blocks[0]["data"]["text"] == "我们分享了与社区共同开展的研究进展。"


def test_normalizer_rejects_english_article_pages_for_chinese_requests() -> None:
    payload = json.loads((FIXTURES / "news-list.json").read_text())
    item = parse_articles_api_payload(payload, date(2026, 10, 1))[0]
    document = (FIXTURES / "article.html").read_text().replace('lang="zh-Hans-CN"', 'lang="en"')

    with pytest.raises(ValueError, match="Chinese article request"):
        normalize_openai_news_item(item, document)


def test_normalizer_uses_chinese_listing_title_when_page_heading_is_english() -> None:
    payload = json.loads((FIXTURES / "news-list.json").read_text())
    item = parse_articles_api_payload(payload, date(2026, 10, 1))[0]
    document = (FIXTURES / "article.html").read_text()
    document = document.replace("携手学术界，深化科学认识", "Building scientific understanding")
    document = document.replace("与学术界合作，推动科学理解。", "Working with academic communities")

    article = normalize_openai_news_item(item, document)

    assert article.title == "携手学术界，深化科学认识"
    assert article.summary == "OpenAI 分享研究成果及合作方式。"


def test_normalizer_omits_english_summary_and_rejects_all_english_article_text() -> None:
    payload = json.loads((FIXTURES / "news-list.json").read_text())
    item = parse_articles_api_payload(payload, date(2026, 10, 1))[0]
    document = (FIXTURES / "article.html").read_text()
    document = document.replace("与学术界合作，推动科学理解。", "Working with academic communities")

    article = normalize_openai_news_item(item, document)
    assert article.summary == "OpenAI 分享研究成果及合作方式。"

    english_item = item.__class__(
        external_id="english-only",
        title="Building scientific understanding",
        canonical_url=item.canonical_url,
        published_at=item.published_at,
        topics=item.topics,
        summary="Working with academic communities",
        raw_payload={},
    )
    english_document = document.replace(
        "携手学术界，深化科学认识", "Building scientific understanding"
    )
    english_document = english_document.replace(
        "我们分享了与社区共同开展的研究进展。", "We share research progress with the community."
    )

    with pytest.raises(ValueError, match="no Chinese title"):
        normalize_openai_news_item(english_item, english_document)


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
