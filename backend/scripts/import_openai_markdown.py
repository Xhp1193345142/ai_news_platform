import argparse
from dataclasses import replace
from pathlib import Path

from app.collectors.openai import normalize_openai_markdown
from scripts.import_openai_fixtures import FIXTURE_DIR, import_articles

ARTICLE_FILES = {
    "gpt-5-6": "gpt.md",
    "samsung-electronics-chatgpt-codex-deployment": "samsung.md",
}

OFFICIAL_CATEGORIES = {
    "gpt-5-6": ["产品", "发布"],
    "samsung-electronics-chatgpt-codex-deployment": ["公司"],
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import source-preserving OpenAI Markdown into PostgreSQL and MinIO."
    )
    parser.add_argument("directory", type=Path, help="Directory containing gpt.md and samsung.md")
    args = parser.parse_args()

    articles = []
    for fixture_path in sorted(FIXTURE_DIR.glob("*.json")):
        import json

        payload = json.loads(fixture_path.read_text())
        external_id = payload["externalId"]
        source_path = args.directory / ARTICLE_FILES[external_id]
        markdown = source_path.read_text()
        payload["topics"] = OFFICIAL_CATEGORIES[external_id]
        payload["summary"] = None
        normalized = normalize_openai_markdown(payload, markdown)
        articles.append(
            replace(normalized, raw_payload={**normalized.raw_payload, "source": "openai"})
        )

    import_articles(articles)


if __name__ == "__main__":
    main()
