from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLayoutProfile:
    source_key: str
    content_root: str
    block_types: tuple[str, ...]
    grouped_components: tuple[str, ...]
    media_policy: str
    fallback_policy: str


OPENAI_LAYOUT_PROFILE = SourceLayoutProfile(
    source_key="openai",
    content_root=(
        "OpenAI News RSS or /backend/articles/ listing → index article HTML / Next.js RSC payload"
    ),
    block_types=(
        "paragraph",
        "heading",
        "list",
        "quote",
        "image",
        "video_embed",
        "media_tabs",
        "chart_tabs",
        "image_carousel",
        "table",
        "source_link",
        "unsupported_embed",
    ),
    grouped_components=(
        "interactive demos use a pill tablist and one active player",
        "benchmark charts use source Vega-Lite specs grouped by source tabs",
        "presentation examples use ordered slide carousels",
    ),
    media_policy=("Archive the raw HTML in MinIO, mirror images, and retain trusted Vimeo embeds."),
    fallback_policy=("Use Chinese source pages; preserve order and link unsupported components."),
)


SOURCE_LAYOUT_PROFILES = {OPENAI_LAYOUT_PROFILE.source_key: OPENAI_LAYOUT_PROFILE}
