"""OpenAI news discovery and article-page collection."""

import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import httpx

from app.collectors.openai import NormalizedArticle
from app.collectors.openai_media import extract_openai_chart_specs, extract_openai_videos

OPENAI_BASE_URL = "https://openai.com"
OPENAI_RSS_URL = f"{OPENAI_BASE_URL}/news/rss.xml"
OPENAI_ARTICLES_API = f"{OPENAI_BASE_URL}/backend/articles/"
OPENAI_CATEGORY_SLUGS = (
    "company",
    "research",
    "product",
    "engineering",
    "safety",
    "security",
    "ai-adoption",
    "applied-ai",
    "global-affairs-news-listed",
    "intelligence-age",
)
OPENAI_CATEGORY_NAMES = {
    "company": "公司",
    "research": "研究",
    "product": "产品",
    "engineering": "工程",
    "safety": "安全",
    "security": "安全防护",
    "ai-adoption": "AI 采用",
    "applied-ai": "应用 AI",
    "global-affairs-news-listed": "全球事务",
    "intelligence-age": "智能时代",
    "publication": "刊发",
    "release": "发布",
}
RSS_CATEGORY_NAMES = {
    "Company": "公司",
    "Research": "研究",
    "Product": "产品",
    "Engineering": "工程",
    "Safety": "安全",
    "Security": "安全防护",
    "AI Adoption": "AI 采用",
    "Applied AI": "应用 AI",
    "Global Affairs": "全球事务",
    "Publication": "刊发",
    "Release": "发布",
}


@dataclass(frozen=True)
class OpenAINewsItem:
    external_id: str
    title: str
    canonical_url: str
    published_at: datetime
    topics: list[str]
    summary: str | None = None
    language: str = "zh-Hans-CN"
    raw_payload: dict[str, Any] | None = None


def parse_publication_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def publication_is_since(value: str, since: date) -> bool:
    """Compare the source's published calendar date, including naive CMS dates."""
    return date.fromisoformat(value[:10]) >= since


def month_start(today: date | None = None) -> date:
    current = today or datetime.now(ZoneInfo("Asia/Shanghai")).date()
    return current.replace(day=1)


def _canonical_url(value: str) -> str:
    absolute_url = urljoin(OPENAI_BASE_URL, value)
    parts = urlsplit(absolute_url)
    if parts.netloc.lower() != "openai.com" and not parts.netloc.lower().endswith(".openai.com"):
        raise ValueError(f"unexpected OpenAI article host: {parts.netloc}")
    path = parts.path
    if path.startswith("/index/"):
        path = f"/zh-Hans-CN{path}"
    return urljoin(OPENAI_BASE_URL, path.rstrip("/") + "/")


def _categories(value: Any) -> list[str]:
    result: list[str] = []
    for category in value if isinstance(value, list) else []:
        if isinstance(category, dict):
            slug = category.get("slug")
            name = category.get("name")
            label = OPENAI_CATEGORY_NAMES.get(slug, name)
        else:
            label = RSS_CATEGORY_NAMES.get(str(category), str(category))
        if isinstance(label, str) and label and label not in result:
            result.append(label)
    return result


def parse_articles_api_payload(payload: dict[str, Any], since: date) -> list[OpenAINewsItem]:
    """Parse the observed OpenAI list API shape: total/items/skip/limit."""
    rows = payload.get("items")
    if not isinstance(rows, list):
        raise ValueError("OpenAI articles response is missing its items array")
    result: list[OpenAINewsItem] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("pageType") != "Article":
            continue
        published = row.get("publicationDate")
        slug = row.get("slug")
        if not isinstance(published, str) or not isinstance(slug, str):
            continue
        if not publication_is_since(published, since):
            continue
        seo_fields = row.get("seoFields")
        summary = seo_fields.get("metaDescription") if isinstance(seo_fields, dict) else None
        result.append(
            OpenAINewsItem(
                external_id=str(row.get("id") or slug),
                title=str(row.get("title") or "").strip(),
                canonical_url=_canonical_url(f"/zh-Hans-CN/{slug}"),
                published_at=parse_publication_date(published),
                topics=_categories(row.get("categories")),
                summary=summary if isinstance(summary, str) else None,
                raw_payload=row,
            )
        )
    return [item for item in result if item.title]


def parse_openai_rss(xml_document: str, since: date) -> list[OpenAINewsItem]:
    root = ET.fromstring(xml_document)
    rows: list[OpenAINewsItem] = []
    for item in root.findall("./channel/item"):
        title = unescape(item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        published = (item.findtext("pubDate") or "").strip()
        if not title or not url or not published:
            continue
        published_at = datetime.strptime(published, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=UTC)
        if published_at.date() < since:
            continue
        rows.append(
            OpenAINewsItem(
                external_id=urlsplit(url).path.strip("/").split("/")[-1],
                title=title,
                canonical_url=_canonical_url(url),
                published_at=published_at,
                topics=_categories([category.text or "" for category in item.findall("category")]),
                summary=(item.findtext("description") or "").strip() or None,
                language="en",
                raw_payload={
                    "title": title,
                    "link": url,
                    "pubDate": published,
                    "categories": [category.text or "" for category in item.findall("category")],
                    "description": item.findtext("description"),
                },
            )
        )
    return rows


class _ArticleHTMLParser(HTMLParser):
    """Small tree builder for the semantic blocks used in OpenAI article pages."""

    VOID = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, Any]] = [{"tag": "root", "attrs": {}, "children": []}]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = {"tag": tag, "attrs": dict(attrs), "children": []}
        self.stack[-1]["children"].append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.stack[-1]["children"].append({"tag": tag, "attrs": dict(attrs), "children": []})

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.stack[-1]["children"].append(data)


def _plain_text(node: dict[str, Any]) -> str:
    parts: list[str] = []
    for child in node["children"]:
        parts.append(_plain_text(child) if isinstance(child, dict) else child)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _node_text_with_links(node: dict[str, Any], base_url: str) -> tuple[str, list[dict[str, str]]]:
    text_parts: list[str] = []
    links: list[dict[str, str]] = []

    def visit(current: dict[str, Any]) -> None:
        tag = current["tag"]
        if tag == "br":
            text_parts.append(" ")
            return
        start = len(text_parts)
        for child in current["children"]:
            if isinstance(child, dict):
                visit(child)
            else:
                text_parts.append(child)
        if tag == "a":
            href = current["attrs"].get("href")
            label = "".join(text_parts[start:]).strip()
            if href and label:
                links.append({"text": label, "url": urljoin(base_url, href)})

    visit(node)
    text = re.sub(r"\s+", " ", "".join(text_parts)).strip()
    return text, links


def _list_data(node: dict[str, Any], base_url: str) -> dict[str, Any]:
    items: list[str] = []
    for child in node["children"]:
        if isinstance(child, dict) and child["tag"] == "li":
            text, _ = _node_text_with_links(child, base_url)
            if text:
                items.append(text)
    return {"items": items, "ordered": node["tag"] == "ol"}


def _is_toc_list(node: dict[str, Any]) -> bool:
    list_items = [
        child for child in node["children"] if isinstance(child, dict) and child["tag"] == "li"
    ]
    if len(list_items) < 2:
        return False
    for item in list_items:
        anchor = _find_first(item, "a")
        if anchor is None or not str(anchor["attrs"].get("href", "")).startswith("#"):
            return False
    return True


def _find_first(node: dict[str, Any], tag: str) -> dict[str, Any] | None:
    if node["tag"] == tag:
        return node
    for child in node["children"]:
        if isinstance(child, dict):
            found = _find_first(child, tag)
            if found:
                return found
    return None


def _chart_groups(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    language_charts: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    for spec in specs:
        title_value = spec.get("title")
        raw_title = (
            title_value
            if isinstance(title_value, str)
            else title_value.get("text")
            if isinstance(title_value, dict)
            else None
        )
        if not isinstance(raw_title, str) or not raw_title:
            continue
        language_match = re.match(r"^SQLite 测试通过率\s*[—-]\s*(.+)$", raw_title)
        item = {"label": language_match.group(1) if language_match else raw_title, "spec": spec}
        if language_match:
            language_charts.append(item)
        else:
            groups.append({"key": raw_title, "match": raw_title, "items": [item]})
    if language_charts:
        groups.append(
            {
                "key": "sqlite-language-benchmarks",
                "match": "SQLite 测试通过率",
                "items": language_charts,
            }
        )
    return groups


def _find_main(node: dict[str, Any]) -> dict[str, Any] | None:
    if node["tag"] == "main":
        return node
    for child in node["children"]:
        if isinstance(child, dict):
            found = _find_main(child)
            if found:
                return found
    return None


def html_article_to_blocks(
    document: str, canonical_url: str, chart_specs: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    parser = _ArticleHTMLParser()
    parser.feed(document)
    main = _find_main(parser.stack[0])
    if main is None:
        raise ValueError("OpenAI article HTML has no main content landmark")
    heading = _find_first(main, "h1")
    if heading is None:
        raise ValueError("OpenAI article HTML has no article title")
    blocks: list[dict[str, Any]] = []
    chart_groups = _chart_groups(chart_specs or [])
    used_chart_groups: set[str] = set()
    stop_headings = {"author", "keep reading", "作者", "继续阅读"}
    body_started = False

    def append(kind: str, data: dict[str, Any]) -> None:
        blocks.append({"id": f"openai-{len(blocks) + 1:04d}-{kind}", "type": kind, "data": data})

    def traverse(node: dict[str, Any]) -> None:
        nonlocal body_started
        tag = node["tag"]
        if tag in {"nav", "aside", "script", "style", "footer"}:
            return
        if tag == "h1":
            body_started = True
            return
        if not body_started:
            for child in node["children"]:
                if isinstance(child, dict):
                    traverse(child)
            return
        if tag in {"h2", "h3", "h4"}:
            text = _plain_text(node)
            if text.lower() in stop_headings:
                body_started = False
                return
            if text:
                append("heading", {"level": int(tag[1]), "text": text})
            return
        if tag == "ul" or tag == "ol":
            if _is_toc_list(node):
                return
            data = _list_data(node, canonical_url)
            if data["items"]:
                append("list", data)
            return
        if tag == "p":
            text, links = _node_text_with_links(node, canonical_url)
            if text:
                data: dict[str, Any] = {"text": text}
                if links:
                    data["links"] = links
                append("paragraph", data)
            return
        if tag == "blockquote":
            text = _plain_text(node)
            if text:
                append("quote", {"text": text, "attribution": None})
            return
        if tag == "img":
            src = node["attrs"].get("src") or node["attrs"].get("data-src")
            if src:
                append(
                    "image",
                    {"url": urljoin(canonical_url, src), "alt": node["attrs"].get("alt", "")},
                )
            return
        if tag == "iframe":
            src = node["attrs"].get("src", "")
            if src.startswith("https://player.vimeo.com/"):
                append(
                    "video_embed",
                    {
                        "provider": "vimeo",
                        "embed_url": src,
                        "source_url": src,
                        "alt": node["attrs"].get("title", ""),
                    },
                )
            else:
                append(
                    "unsupported_embed",
                    {
                        "component": "iframe",
                        "source_url": src,
                        "alt": node["attrs"].get("title", ""),
                        "fallback_url": canonical_url,
                    },
                )
            return
        if tag == "figure":
            figure_text = _plain_text(node)
            chart_group = next(
                (
                    group
                    for group in chart_groups
                    if group["key"] not in used_chart_groups and group["match"] in figure_text
                ),
                None,
            )
            if chart_group:
                append("chart_tabs", {"items": chart_group["items"]})
                used_chart_groups.add(chart_group["key"])
                return
            image = _find_first(node, "img")
            if image:
                traverse(image)
                return
        for child in node["children"]:
            if isinstance(child, dict):
                traverse(child)

    traverse(main)
    for group in chart_groups:
        if group["key"] not in used_chart_groups:
            append(
                "unsupported_embed",
                {
                    "component": "vegaLiteSpec",
                    "label": "OpenAI 交互式图表",
                    "description": "图表数据已保留，但页面中的选项卡位置未能可靠识别。",
                    "items": group["items"],
                    "fallback_url": canonical_url,
                },
            )
    append("source_link", {"label": "在 OpenAI 阅读完整原文", "url": canonical_url})
    return blocks


def html_article_metadata(document: str) -> tuple[str | None, str | None]:
    parser = _ArticleHTMLParser()
    parser.feed(document)
    main = _find_main(parser.stack[0])
    title_node = _find_first(main, "h1") if main else None
    html_node = _find_first(parser.stack[0], "html")
    title = _plain_text(title_node) if title_node else None
    language = html_node["attrs"].get("lang") if html_node else None
    return title or None, language


def normalize_openai_news_item(item: OpenAINewsItem, document: str) -> NormalizedArticle:
    chart_specs = extract_openai_chart_specs(document)
    blocks = html_article_to_blocks(document, item.canonical_url, chart_specs)
    rendered_video_urls = {
        block.get("data", {}).get("embed_url")
        for block in blocks
        if block.get("type") == "video_embed"
    }
    for video in extract_openai_videos(document):
        if video.embed_url not in rendered_video_urls:
            blocks.insert(
                -1,
                {
                    "id": f"openai-{len(blocks):04d}-unsupported_embed",
                    "type": "unsupported_embed",
                    "data": {
                        "component": "RSC video embed",
                        "source_url": video.embed_url,
                        "alt": video.alt,
                        "label": video.alt or "OpenAI 交互式演示",
                        "description": "演示媒体已保留，当前页面结构未能可靠恢复其官网标签分组。",
                        "fallback_url": item.canonical_url,
                    },
                },
            )
    source_title, source_language = html_article_metadata(document)
    title = source_title or item.title
    language = source_language or item.language
    raw_payload = {
        "source": "openai",
        "listing": item.raw_payload or {},
        "canonicalUrl": item.canonical_url,
        "title": title,
        "publishedAt": item.published_at.isoformat(),
        "topics": item.topics,
        "rawHtmlSha256": hashlib.sha256(document.encode()).hexdigest(),
    }
    content_hash = hashlib.sha256(
        json.dumps({"title": title, "blocks": blocks}, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    return NormalizedArticle(
        external_id=item.external_id,
        source_key="openai",
        canonical_url=item.canonical_url,
        title=title,
        subtitle=None,
        summary=item.summary,
        author_name="OpenAI",
        published_at=item.published_at,
        language=language,
        topics=item.topics,
        content_blocks=blocks,
        metrics={},
        raw_payload=raw_payload,
        content_hash=content_hash,
    )


class OpenAINewsClient:
    def __init__(self, client: httpx.Client | None = None, cookie: str | None = None) -> None:
        headers = {
            "Accept": (
                "text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8"
            ),
            "User-Agent": "AI-Signal/0.1 (+OpenAI news reader)",
        }
        if cookie:
            headers["Cookie"] = cookie
        self.has_cookie = bool(cookie)
        self.client = client or httpx.Client(headers=headers, follow_redirects=True, timeout=30)
        self.retry_count = 0

    def __enter__(self) -> "OpenAINewsClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.client.close()

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        response: httpx.Response | None = None
        for attempt in range(3):
            try:
                response = self.client.get(url, **kwargs)
                if response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                    return response
            except httpx.TransportError:
                if attempt == 2:
                    raise
            self.retry_count += 1
            time.sleep(0.1 * (2**attempt))
        assert response is not None
        return response

    def list_articles(self, since: date) -> list[OpenAINewsItem]:
        if self.has_cookie:
            page_queries = json.dumps(
                [{"pageTypes": ["Article"], "categories": list(OPENAI_CATEGORY_SLUGS)}],
                separators=(",", ":"),
            )
            rows: list[OpenAINewsItem] = []
            for skip in range(0, 5000, 9):
                response = self.get(
                    OPENAI_ARTICLES_API,
                    params={
                        "locale": "zh-Hans-CN",
                        "pageQueries": page_queries,
                        "limit": 9,
                        "skip": skip,
                        "sort": "new",
                        "groupedTags": "",
                        "search": "",
                    },
                    headers={"Referer": f"{OPENAI_BASE_URL}/zh-Hans-CN/news/"},
                )
                if response.status_code == 403:
                    break
                response.raise_for_status()
                payload = response.json()
                page = parse_articles_api_payload(payload, since)
                rows.extend(page)
                items = payload.get("items", [])
                if (
                    not items
                    or len(items) < 9
                    or any(
                        isinstance(item, dict)
                        and isinstance(item.get("publicationDate"), str)
                        and not publication_is_since(item["publicationDate"], since)
                        for item in items
                    )
                ):
                    break
            if rows:
                return _deduplicate_items(rows)
        response = self.get(OPENAI_RSS_URL)
        response.raise_for_status()
        return _deduplicate_items(parse_openai_rss(response.text, since))

    def fetch_article(self, item: OpenAINewsItem) -> str:
        response = self.get(item.canonical_url)
        if response.status_code == 403 and response.headers.get("cf-mitigated") == "challenge":
            raise RuntimeError(
                "Cloudflare challenged the article request; set a current OPENAI_COOKIE or retry "
                "from an allowed network."
            )
        response.raise_for_status()
        return response.text

    def fetch_asset(self, url: str) -> httpx.Response:
        response = self.get(url)
        response.raise_for_status()
        return response


def _deduplicate_items(items: list[OpenAINewsItem]) -> list[OpenAINewsItem]:
    unique: dict[str, OpenAINewsItem] = {}
    for item in items:
        unique.setdefault(item.canonical_url, item)
    return sorted(unique.values(), key=lambda item: item.published_at, reverse=True)
