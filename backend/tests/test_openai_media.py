import json

from app.collectors.openai_media import extract_openai_chart_specs, extract_openai_videos


def test_extract_openai_vimeo_media_from_rsc_payload() -> None:
    document = (
        r"{\"altText\":\"演示视频\",\"videoEmbedUrl\":\""
        r"https://player.vimeo.com/video/123?h=abc\u0026amp;badge=0\"}"
    )
    videos = extract_openai_videos(document)
    assert len(videos) == 1
    assert videos[0].alt == "演示视频"
    assert videos[0].embed_url == "https://player.vimeo.com/video/123?h=abc&badge=0"


def test_extract_openai_videos_deduplicates_embed_url() -> None:
    media = r"{\"altText\":\"A\",\"videoEmbedUrl\":\"https://player.vimeo.com/video/1\"}"
    assert len(extract_openai_videos(media + media)) == 1


def test_extract_openai_chart_specs_from_rsc_payload() -> None:
    payload = (
        '42:["$","chart",null,{"vegaLiteSpec":'
        '{"$schema":"https://vega.github.io/schema/vega-lite/v6.json",'
        '"title":{"text":"BrowseComp"},"data":{"values":[{"score":92.2}]},'
        '"mark":"line","encoding":{}}}]'
    )
    encoded = json.dumps(payload, ensure_ascii=False)
    document = f"<html><script>self.__next_f.push([1, {encoded}])</script></html>"

    specs = extract_openai_chart_specs(document)

    assert len(specs) == 1
    assert specs[0]["title"]["text"] == "BrowseComp"
    assert specs[0]["data"]["values"] == [{"score": 92.2}]


def test_extract_openai_chart_specs_accepts_string_titles_from_source() -> None:
    payload = (
        '42:["$","chart",null,{"vegaLiteSpec":'
        '{"$schema":"https://vega.github.io/schema/vega-lite/v6.json",'
        '"title":"平均测试通过率","data":{"values":[{"score":92.2}]},'
        '"mark":"bar","encoding":{}}}]'
    )
    encoded = json.dumps(payload, ensure_ascii=False)
    document = f"<html><script>self.__next_f.push([1, {encoded}])</script></html>"

    specs = extract_openai_chart_specs(document)

    assert len(specs) == 1
    assert specs[0]["title"] == "平均测试通过率"
