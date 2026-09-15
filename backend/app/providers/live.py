import asyncio
import time
import httpx
from .base import MarketDataProvider
from ..models import OrderBook, Level, now_ms
from .mock import FEES


class RestProvider(MarketDataProvider):
    source = "live"

    def __init__(self, name):
        self.name = name
        self.client = httpx.AsyncClient(timeout=6)
        self.sequence = 0

    async def fetch(self):
        books = []
        for base in ["BTC", "ETH", "SOL"]:
            started = time.perf_counter()
            pair = base + "USDT"
            if self.name == "Binance":
                url, params = "https://data-api.binance.vision/api/v3/depth", {
                    "symbol": pair,
                    "limit": 20,
                }
            elif self.name == "Coinbase":
                url, params = (
                    f"https://api.exchange.coinbase.com/products/{base}-USDT/book",
                    {"level": 2},
                )
            elif self.name == "Kraken":
                url, params = "https://api.kraken.com/0/public/Depth", {
                    "pair": ("XBT" if base == "BTC" else base) + "USDT",
                    "count": 20,
                }
            elif self.name == "OKX":
                url, params = "https://www.okx.com/api/v5/market/books", {
                    "instId": base + "-USDT",
                    "sz": 20,
                }
            else:
                url, params = "https://api.bybit.com/v5/market/orderbook", {
                    "category": "spot",
                    "symbol": pair,
                    "limit": 50,
                }
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            stamp = now_ms()
            latency = (time.perf_counter() - started) * 1000
            if self.name == "Kraken":
                if data.get("error"):
                    raise ValueError(str(data["error"]))
                data = next(iter(data["result"].values()))
            elif self.name == "OKX":
                if data.get("code") != "0":
                    raise ValueError(data.get("msg", "OKX data error"))
                data = data["data"][0]
            elif self.name == "Bybit":
                if data.get("retCode") != 0:
                    raise ValueError(data.get("retMsg", "Bybit data error"))
                data = data["result"]
                data = {**data, "bids": data["b"], "asks": data["a"]}
            self.sequence += 1
            timestamp = int(data.get("ts", stamp - int(latency)))
            # Conservative request-start time where provider lacks a snapshot timestamp.
            books.append(
                OrderBook(
                    exchange=self.name,
                    symbol=f"{base}/USDT",
                    base=base,
                    quote="USDT",
                    bids=[
                        Level(price=float(x[0]), quantity=float(x[1]))
                        for x in data["bids"][:20]
                    ],
                    asks=[
                        Level(price=float(x[0]), quantity=float(x[1]))
                        for x in data["asks"][:20]
                    ],
                    timestamp=timestamp,
                    received_at=stamp,
                    sequence=str(
                        data.get("lastUpdateId", data.get("sequence", self.sequence))
                    ),
                    latency_ms=latency,
                    fee_rate=FEES[self.name],
                    source="live",
                    instrument_id=f"{base}:USDT:crypto",
                )
            )
            await asyncio.sleep(0.12)
        return books

    async def close(self):
        await self.client.aclose()


class BinanceProvider(RestProvider):
    def __init__(self):
        super().__init__("Binance")


class CoinbaseProvider(RestProvider):
    def __init__(self):
        super().__init__("Coinbase")


class KrakenProvider(RestProvider):
    def __init__(self):
        super().__init__("Kraken")


class StockProvider(MarketDataProvider):
    name = "Stocks"
    source = "live"

    async def fetch(self):
        raise RuntimeError(
            "Licensed equity depth provider not configured. Live US/Indian equities disabled."
        )


# Native public partial-depth stream. Full snapshots avoid local delta merge drift.
class BinanceStreamingProvider(BinanceProvider):
    async def stream(self):
        import json
        import websockets

        streams = "/".join(
            f"{base.lower()}usdt@depth20@100ms" for base in ["BTC", "ETH", "SOL"]
        )
        url = "wss://stream.binance.com:9443/stream?streams=" + streams
        async with websockets.connect(
            url, ping_interval=20, ping_timeout=10, open_timeout=6, max_queue=4
        ) as socket:
            async for raw in socket:
                envelope = json.loads(raw)
                data = envelope["data"]
                base = envelope["stream"].split("usdt@")[0].upper()
                stamp = now_ms()
                yield OrderBook(
                    exchange="Binance",
                    symbol=f"{base}/USDT",
                    base=base,
                    quote="USDT",
                    bids=[
                        Level(price=float(p), quantity=float(q))
                        for p, q in data["bids"]
                        if float(q) > 0
                    ],
                    asks=[
                        Level(price=float(p), quantity=float(q))
                        for p, q in data["asks"]
                        if float(q) > 0
                    ],
                    timestamp=stamp,
                    received_at=stamp,
                    sequence=str(data["lastUpdateId"]),
                    latency_ms=socket.latency * 1000,
                    fee_rate=FEES["Binance"],
                    source="live",
                    instrument_id=f"{base}:USDT:crypto",
                    timestamp_origin="received",
                    exchange_timestamp=None,
                )
