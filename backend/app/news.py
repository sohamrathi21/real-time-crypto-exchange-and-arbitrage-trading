"""Publisher RSS headlines; no generated stories or fabricated freshness."""

import asyncio
import hashlib
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import httpx

FEEDS = {
    "Global": ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    "Asia": ("BBC Asia", "https://feeds.bbci.co.uk/news/world/asia/rss.xml"),
    "Europe": ("BBC Europe", "https://feeds.bbci.co.uk/news/world/europe/rss.xml"),
    "Africa": ("BBC Africa", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"),
    "North America": (
        "BBC US & Canada",
        "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
    ),
    "South America": (
        "BBC Latin America",
        "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml",
    ),
    "Oceania": (
        "BBC Australia",
        "https://feeds.bbci.co.uk/news/world/australia/rss.xml",
    ),
    "Middle East": (
        "BBC Middle East",
        "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
    ),
    "Crypto": ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
}


def parse_feed(raw, region, source):
    if (
        len(raw) > 2_000_000
        or b"<!DOCTYPE" in raw.upper()
        or b"<!ENTITY" in raw.upper()
    ):
        raise ValueError("Unsupported feed document")
    rows = []
    for item in ET.fromstring(raw).findall("./channel/item")[:25]:
        title, link = (item.findtext("title") or "").strip(), (
            item.findtext("link") or ""
        ).strip()
        url = urlparse(link)
        if (
            not title
            or url.scheme != "https"
            or not any(
                url.hostname == d or (url.hostname or "").endswith("." + d)
                for d in ("bbc.com", "bbc.co.uk", "coindesk.com")
            )
        ):
            continue
        try:
            date = parsedate_to_datetime(item.findtext("pubDate") or "")
            stamp = int(
                date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp() * 1000
            )
        except (ValueError, TypeError, OverflowError):
            stamp = None
        rows.append(
            {
                "id": hashlib.sha256(link.encode()).hexdigest()[:20],
                "headline": title[:500],
                "url": link,
                "source": source,
                "region": region,
                "published_at": stamp,
            }
        )
    if not rows:
        raise ValueError("No valid headlines in feed")
    return rows


class NewsService:
    def __init__(self, transport=None):
        self.cache = {}
        self.checked = 0
        self.lock = asyncio.Lock()
        self.transport = transport

    async def snapshot(self):
        async with self.lock:
            if time.monotonic() - self.checked > 300 or not self.checked:
                async with httpx.AsyncClient(
                    timeout=10,
                    follow_redirects=True,
                    transport=self.transport,
                    headers={"User-Agent": "ArbitrageX/1.0 RSS reader"},
                ) as client:

                    async def fetch(region, source, url):
                        previous = self.cache.get(region, {})
                        try:
                            async with client.stream("GET", url) as response:
                                response.raise_for_status()
                                raw = bytearray()
                                async for part in response.aiter_bytes():
                                    raw.extend(part)
                                    if len(raw) > 2_000_000:
                                        raise ValueError("Feed too large")
                            items = parse_feed(bytes(raw), region, source)
                            self.cache[region] = {
                                "source": source,
                                "region": region,
                                "status": "available",
                                "fetched_at": int(time.time() * 1000),
                                "items": items,
                            }
                        except Exception as exc:
                            self.cache[region] = {
                                **previous,
                                "source": source,
                                "region": region,
                                "status": (
                                    "cached" if previous.get("items") else "unavailable"
                                ),
                                "error": type(exc).__name__,
                                "items": previous.get("items", []),
                            }

                    await asyncio.gather(
                        *(fetch(region, *feed) for region, feed in FEEDS.items())
                    )
                self.checked = time.monotonic()
        return {
            "feeds": list(self.cache.values()),
            "refresh_seconds": 300,
            "timestamp": int(time.time() * 1000),
        }
