import json
import logging
from redis.asyncio import Redis

log = logging.getLogger(__name__)


class MarketCache:
    def __init__(self, url):
        self.books = {}
        self.redis = (
            Redis.from_url(
                url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
            )
            if url
            else None
        )
        self.status = "memory (local mode)" if not url else "connecting"

    def ingest(self, book):
        key = (book.exchange, book.symbol)
        previous = self.books.get(key)
        if (
            previous
            and previous.source == book.source
            and (
                previous.sequence == book.sequence
                or previous.timestamp > book.timestamp
            )
        ):
            return False
        self.books[key] = book
        return True

    async def publish(self, payload):
        if not self.redis:
            return
        try:
            async with self.redis.pipeline(transaction=False) as pipe:
                for (exchange, symbol), book in self.books.items():
                    pipe.set(f"book:{exchange}:{symbol}", book.model_dump_json(), ex=15)
                    pipe.set(
                        f"price:{exchange}:{symbol}",
                        json.dumps(
                            {
                                "bid": book.bids[0].price,
                                "ask": book.asks[0].price,
                                "timestamp": book.timestamp,
                            }
                        ),
                        ex=15,
                    )
                pipe.set("opportunities", json.dumps(payload["opportunities"]), ex=10)
                pipe.publish("market:updates", json.dumps(payload))
                await pipe.execute()
            self.status = "connected"
        except Exception as exc:
            self.status = "degraded: in-memory fallback"
            log.warning(json.dumps({"event": "redis_unavailable", "error": str(exc)}))

    async def close(self):
        if self.redis:
            await self.redis.aclose()
