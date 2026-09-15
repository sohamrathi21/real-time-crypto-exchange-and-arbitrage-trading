import httpx
import pytest
from backend.app.news import NewsService, parse_feed

RSS = b"<rss><channel><item><title>Published headline</title><link>https://www.bbc.com/news/article</link><pubDate>Tue, 15 Sep 2026 06:00:00 GMT</pubDate></item><item><title>Unsafe</title><link>javascript:alert(1)</link></item></channel></rss>"


def test_news_preserves_publisher_url_time_and_rejects_unsafe_link():
    items = parse_feed(RSS, "Asia", "BBC Asia")
    assert len(items) == 1
    assert items[0]["published_at"] == 1789452000000
    assert items[0]["url"] == "https://www.bbc.com/news/article"


def test_news_rejects_entity_documents():
    with pytest.raises(ValueError):
        parse_feed(b'<!DOCTYPE rss [<!ENTITY e "boom">]><rss/>', "Asia", "BBC")


@pytest.mark.asyncio
async def test_news_retains_original_time_on_outage_and_caches_requests():
    count = 0
    outage = False

    def handle(req):
        nonlocal count
        count += 1
        return httpx.Response(503 if outage else 200, content=RSS)

    service = NewsService(httpx.MockTransport(handle))
    first = await service.snapshot()
    calls = count
    await service.snapshot()
    assert count == calls
    outage = True
    service.checked = 0
    second = await service.snapshot()
    assert all(f["status"] == "cached" for f in second["feeds"])
    assert (
        second["feeds"][0]["items"][0]["published_at"]
        == first["feeds"][0]["items"][0]["published_at"]
    )
