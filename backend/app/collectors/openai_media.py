import html
import json
import re
from dataclasses import dataclass
from typing import Any

VIDEO_PATTERN = re.compile(
    r'\\"altText\\":\\"(?P<alt>.*?)\\",\\"videoEmbedUrl\\":\\"'
    r'(?P<url>https://player\.vimeo\.com/video/.*?)\\"'
)
SCRIPT_PATTERN = re.compile(r"<script>(?P<body>.*?)</script>", re.DOTALL)
PUSH_PAYLOAD_PATTERN = re.compile(
    r'self\.__next_f\.push\(\[1,\s*(?P<payload>"(?:\\.|[^"])*")\]\)',
    re.DOTALL,
)


@dataclass(frozen=True)
class OpenAIVideo:
    embed_url: str
    alt: str


def extract_openai_videos(document: str) -> list[OpenAIVideo]:
    videos: list[OpenAIVideo] = []
    seen: set[str] = set()
    for match in VIDEO_PATTERN.finditer(document):
        url = html.unescape(match["url"].replace("\\u0026", "&"))
        alt = html.unescape(match["alt"].replace("“”", "GPT-5.6 介绍视频"))
        if url not in seen:
            videos.append(OpenAIVideo(embed_url=url, alt=alt))
            seen.add(url)
    return videos


def extract_openai_chart_specs(document: str) -> list[dict[str, Any]]:
    """Recover source Vega-Lite specs embedded in Next.js RSC payloads."""
    payloads: list[str] = []
    for script_match in SCRIPT_PATTERN.finditer(document):
        payload_match = PUSH_PAYLOAD_PATTERN.search(script_match["body"])
        if payload_match is None:
            continue
        try:
            payloads.append(json.loads(payload_match["payload"]))
        except json.JSONDecodeError:
            continue

    joined_payload = "".join(payloads)
    marker = '"vegaLiteSpec":'
    decoder = json.JSONDecoder()
    specs: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    position = 0
    while (marker_index := joined_payload.find(marker, position)) >= 0:
        value_index = marker_index + len(marker)
        try:
            spec, end_index = decoder.raw_decode(joined_payload, value_index)
        except json.JSONDecodeError:
            position = value_index
            continue
        position = end_index
        if not isinstance(spec, dict):
            continue
        title = spec.get("title", {}).get("text")
        if isinstance(title, str) and title not in seen_titles:
            specs.append(spec)
            seen_titles.add(title)
    return specs
