import asyncio
import json
import logging
import math
import statistics
import time
import uuid
from collections import deque, defaultdict
from .providers.mock import MockProvider, VENUES
from .providers.live import RestProvider, BinanceStreamingProvider
from .models import now_ms
from .cache import MarketCache
from .detector import Detector
from .storage import record
from .automation import EventBus, OpportunityLifecycle
from .replay import ReplaySession

log = logging.getLogger(__name__)


class Scanner:
    def __init__(self, settings, repository, paper):
        self.settings, self.repository, self.paper = settings, repository, paper
        self.bus = EventBus(settings, repository)
        self.lifecycle = OpportunityLifecycle(self.bus)
        self.replay = ReplaySession()
        self.order_engine = None
        self.started_at = now_ms()
        self.cache = MarketCache(settings.redis_url)
        self.detector = Detector(settings)
        self.mock = MockProvider()
        self.providers = (
            [
                BinanceStreamingProvider() if v == "Binance" else RestProvider(v)
                for v in VENUES
            ]
            if settings.data_mode == "live"
            else []
        )
        self.lock = asyncio.Lock()
        self.opportunities = []
        self.alerts, self.history = deque(maxlen=80), deque(maxlen=180)
        self.status = {}
        self.tasks = []
        self.running = False
        self.detection_ms = 0
        self.end_to_end_ms = 0
        self.subscribers = set()
        self.last_snapshot = 0
        self.mid_history = defaultdict(lambda: deque(maxlen=60))
        self.last_rejection_alert = 0
        self.price_history = defaultdict(lambda: deque(maxlen=1800))
        self.persistence_status = "connected"

    def alert(self, kind, message):
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": now_ms(),
            "kind": kind,
            "message": message,
        }
        self.alerts.appendleft(event)
        event_type = {
            "disconnected": "MARKET_DISCONNECTED",
            "stale": "MARKET_DATA_STALE",
            "connected": "MARKET_DATA_RECOVERED",
            "risk": "RISK_LIMIT_TRIGGERED",
            "error": "SYSTEM_ERROR",
        }.get(kind)
        if event_type:
            self.bus.emit(event_type, severity="warning", metadata={"reason": message})
        log.info(json.dumps(event))

    async def provider_loop(self, provider):
        delay = 2
        while self.running:
            try:
                if hasattr(provider, "stream"):
                    try:
                        async for book in provider.stream():
                            async with self.lock:
                                if not self.replay.enabled:
                                    self.cache.ingest(book)
                            self.status[provider.name] = {
                                "state": "connected",
                                "source": "live",
                                "transport": "websocket",
                                "updated_at": now_ms(),
                                "latency_ms": book.latency_ms,
                            }
                        raise RuntimeError("Exchange stream closed")
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        self.alert(
                            "disconnected",
                            f"{provider.name} stream unavailable; trying read-only REST: {str(exc)[:80]}",
                        )
                books = await provider.fetch()
                async with self.lock:
                    for book in books:
                        if not self.replay.enabled:
                            self.cache.ingest(book)
                previous = self.status.get(provider.name, {})
                self.status[provider.name] = {
                    "state": "connected",
                    "source": "live",
                    "updated_at": now_ms(),
                    "latency_ms": max(b.latency_ms for b in books),
                    "transport": "rest",
                }
                self.detector.reliability[provider.name] = min(
                    1, self.detector.reliability.get(provider.name, 0.9) + 0.02
                )
                if previous.get("state") == "disconnected":
                    self.alert("connected", f"{provider.name} recovered")
                delay = 2
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self.status.get(provider.name, {}).get("state") != "disconnected":
                    self.alert(
                        "disconnected",
                        f"{provider.name}: {str(exc)[:160]}. No synthetic fallback is used in live mode.",
                    )
                self.status[provider.name] = {
                    "state": "disconnected",
                    "source": "unavailable",
                    "error": str(exc)[:160],
                    "updated_at": now_ms(),
                }
                self.detector.reliability[provider.name] = 0.5
                delay = min(60, delay * 2)
            await asyncio.sleep(delay)

    async def start(self):
        self.running = True
        await self.bus.start()
        self.tasks = [asyncio.create_task(self.run())] + [
            asyncio.create_task(self.provider_loop(p)) for p in self.providers
        ]

    async def stop(self):
        self.running = False
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        for provider in self.providers:
            await provider.close()
        await self.cache.close()
        await self.bus.stop()

    async def run(self):
        while self.running:
            started = time.perf_counter()
            try:
                demo = (
                    self.replay.tick()
                    if self.replay.enabled
                    else await self.mock.fetch()
                )
                async with self.lock:
                    for book in demo:
                        state = self.status.get(book.exchange, {})
                        if (
                            self.replay.enabled
                            or self.settings.data_mode != "live"
                        ):
                            self.cache.ingest(book)
                    if self.replay.enabled:
                        for venue in {b.exchange for b in self.cache.books.values()}:
                            self.status[venue] = {
                                "state": "replay",
                                "source": "replay",
                                "updated_at": now_ms(),
                            }
                    elif self.settings.data_mode != "live":
                        for venue in VENUES + ["NASDAQ-SIM", "NYSE-SIM"]:
                            self.status[venue] = {
                                "state": "simulated",
                                "source": "demo",
                                "updated_at": now_ms(),
                                "latency_ms": round(
                                    next(
                                        b.latency_ms
                                        for b in demo
                                        if b.exchange == venue
                                    ),
                                    1,
                                ),
                            }
                    else:
                        self.status["Stocks"] = {
                            "state": "disabled",
                            "source": "unavailable",
                            "error": "Licensed equity depth feed not configured",
                        }
                    for book in self.cache.books.values():
                        series = self.price_history[f"{book.exchange}:{book.symbol}"]
                        if not series or series[-1]["timestamp"] != book.timestamp:
                            series.append(
                                {
                                    "timestamp": book.timestamp,
                                    "price": (book.bids[0].price + book.asks[0].price)
                                    / 2,
                                }
                            )
                        self.mid_history[book.symbol].append(
                            (book.bids[0].price + book.asks[0].price) / 2
                        )
                    for symbol, prices in self.mid_history.items():
                        returns = [
                            prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))
                        ]
                        self.detector.volatility[symbol] = (
                            statistics.pstdev(returns) if returns else 0
                        )
                    detect_start = time.perf_counter()
                    previous = {o.id for o in self.opportunities}
                    self.opportunities = self.detector.scan(
                        list(self.cache.books.values())
                    )
                    self.lifecycle.update(self.opportunities)
                    self.detection_ms = (time.perf_counter() - detect_start) * 1000
                    active = {o.id for o in self.opportunities}
                    for op in self.opportunities:
                        if op.id not in previous and op.confidence_score >= 85:
                            self.alert(
                                "opportunity",
                                f"{op.symbol} · {op.net_edge_percent:.3f}% net · confidence {op.confidence_score:.0f}",
                            )
                    disappeared = previous - active
                    if disappeared:
                        self.alert(
                            "expired", f"{len(disappeared)} opportunity routes closed"
                        )
                    if (
                        self.detector.rejected
                        and now_ms() - self.last_rejection_alert > 30000
                    ):
                        self.alert(
                            "risk",
                            f"{self.detector.rejected} candidates excluded by risk or depth limits",
                        )
                        self.last_rejection_alert = now_ms()
                    stale = sum(
                        now_ms() - b.timestamp > self.settings.max_price_age_ms
                        for b in self.cache.books.values()
                    )
                    if stale and not getattr(self, "had_stale", False):
                        self.alert(
                            "stale", f"{stale} stale books excluded from detection"
                        )
                    if not stale and getattr(self, "had_stale", False):
                        self.alert(
                            "connected", "Previously stale market data recovered"
                        )
                    self.had_stale = bool(stale)
                    self.end_to_end_ms = (time.perf_counter() - started) * 1000
                    self.history.append(
                        {
                            "timestamp": now_ms(),
                            "edge": max(
                                (o.net_edge_percent for o in self.opportunities),
                                default=0,
                            ),
                            "count": len(self.opportunities),
                            "latency_ms": self.detection_ms,
                            "pnl": self.paper.portfolio()["realized_pnl"],
                        }
                    )
                payload = self.snapshot()
                for queue in list(self.subscribers):
                    if queue.full():
                        queue.get_nowait()
                    queue.put_nowait(payload)
                await self.cache.publish(payload)
                if (
                    now_ms() - self.last_snapshot
                    >= self.settings.snapshot_interval_seconds * 1000
                ):
                    self.last_snapshot = now_ms()
                    await self.persist()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.alert("error", f"Scanner recovered from error: {str(exc)[:180]}")
            await asyncio.sleep(max(0.05, 1 - (time.perf_counter() - started)))

    async def persist(self):
        stamp = now_ms()
        records = []
        for book in self.cache.books.values():
            fields = dict(symbol=book.symbol, exchange=book.exchange)
            records.extend(
                [
                    record(
                        "market",
                        f"{book.exchange}:{book.symbol}",
                        {
                            "symbol": book.symbol,
                            "exchange": book.exchange,
                            "source": book.source,
                        },
                        **fields,
                    ),
                    record(
                        "asset",
                        book.base,
                        {"symbol": book.base, "asset_class": book.asset_class},
                    ),
                    record("exchange", book.exchange, {"name": book.exchange}),
                    record(
                        "orderbook_snapshot",
                        f"{stamp}:{book.exchange}:{book.symbol}",
                        book.model_dump(),
                        **fields,
                    ),
                    record(
                        "price_snapshot",
                        f"{stamp}:{book.exchange}:{book.symbol}",
                        {
                            "bid": book.bids[0].price,
                            "ask": book.asks[0].price,
                            "source": book.source,
                        },
                        **fields,
                    ),
                ]
            )
        for op in self.opportunities:
            records.append(
                record(
                    "opportunity",
                    op.id,
                    self.lifecycle.active.get(op.id, op.model_dump()),
                    symbol=op.symbol,
                    opportunity_id=op.id,
                    status=self.lifecycle.active.get(op.id, {}).get("status", "ACTIVE"),
                    net_edge=op.net_edge_percent,
                )
            )
            records.append(
                record(
                    "opportunity_history",
                    f"{stamp}:{op.id}",
                    op.model_dump(),
                    symbol=op.symbol,
                    opportunity_id=op.id,
                    net_edge=op.net_edge_percent,
                )
            )
        for expired in self.lifecycle.history:
            records.append(
                record(
                    "opportunity",
                    expired["id"],
                    expired,
                    symbol=expired["symbol"],
                    opportunity_id=expired["id"],
                    status=expired["status"],
                )
            )
        for event in self.alerts:
            records.append(
                record("system_event", event["id"], event, timestamp=event["timestamp"])
            )
        try:
            await self.repository.put_many(records)
            self.persistence_status = "connected"
        except Exception as exc:
            self.persistence_status = "unavailable"
            self.alert("error", f"Database snapshot failed: {str(exc)[:140]}")

    def prices(self):
        return [
            {
                "exchange": b.exchange,
                "symbol": b.symbol,
                "base": b.base,
                "quote": b.quote,
                "bid": b.bids[0].price,
                "ask": b.asks[0].price,
                "bid_size": b.bids[0].quantity,
                "ask_size": b.asks[0].quantity,
                "price": (b.bids[0].price + b.asks[0].price) / 2,
                "spread_percent": (b.asks[0].price / b.bids[0].price - 1) * 100,
                "depth_notional": sum(x.price * x.quantity for x in b.bids + b.asks),
                "change_24h": None,
                "volume_24h": None,
                "source": b.source,
                "asset_class": b.asset_class,
                "exchange_timestamp": b.exchange_timestamp,
                "timestamp_origin": b.timestamp_origin,
                "received_at": b.received_at,
                "last": None,
                "volume": None,
                "data_status": (
                    "STALE"
                    if now_ms() - b.timestamp > self.settings.max_price_age_ms
                    else (
                        "SIMULATED"
                        if b.source == "demo"
                        else "REPLAY" if b.source == "replay" else "LIVE"
                    )
                ),
                "timestamp": b.timestamp,
                "stale": now_ms() - b.timestamp > self.settings.max_price_age_ms,
            }
            for b in self.cache.books.values()
        ]

    def snapshot(self):
        return {
            "timestamp": now_ms(),
            "mode": "replay" if self.replay.enabled else self.settings.data_mode,
            "opportunities": [o.model_dump() for o in self.opportunities],
            "prices": self.prices(),
            "venues": self.status,
            "portfolio": self.paper.portfolio(),
            "trades": list(reversed(self.paper.trades[-100:])),
            "alerts": list(self.alerts),
            "history": list(self.history),
            "detection_ms": round(self.detection_ms, 2),
            "end_to_end_ms": round(self.end_to_end_ms, 2),
            "rejected": self.detector.rejected,
            "redis": self.cache.status,
            "database": self.persistence_status,
            "settings": self.settings.model_dump(
                exclude={
                    "database_url",
                    "redis_url",
                    "automation_token",
                    "n8n_webhook_url",
                }
            ),
            "automation": self.bus.snapshot(),
            "replay": self.replay.snapshot(),
            "execution": (
                self.order_engine.snapshot(self.cache.books)
                if self.order_engine
                else None
            ),
            "system": {
                "uptime_seconds": (now_ms() - self.started_at) / 1000,
                "events_per_second": sum(
                    e["timestamp"] > now_ms() - 1000 for e in self.bus.events
                ),
                "errors": self.bus.failures,
                "detected": self.lifecycle.detected,
                "expired": self.lifecycle.expired,
            },
            "paper_only": True,
        }
