import asyncio
import json
import logging
import uuid
from collections import deque
import httpx
from pydantic import BaseModel, Field
from .models import now_ms
from .storage import record


class AutomationConfig(BaseModel):
    auto_paper_trade: bool = False
    high_confidence_alerts: bool = True
    min_auto_edge: float = Field(0.15, ge=0)
    min_auto_confidence: float = Field(85, ge=0, le=100)
    max_auto_capital: float = Field(10000, gt=0)
    max_daily_paper_trades: int = Field(20, ge=1, le=1000)
    min_liquidity: float = Field(60, ge=0, le=100)


class EventBus:
    def __init__(self, settings, repository):
        self.settings, self.repository = settings, repository
        self.config = AutomationConfig(
            auto_paper_trade=settings.auto_paper_trade,
            min_auto_edge=settings.min_auto_edge,
            min_auto_confidence=settings.min_auto_confidence,
            max_auto_capital=settings.max_auto_capital,
            max_daily_paper_trades=settings.max_daily_paper_trades,
        )
        self.events = deque(maxlen=500)
        self.queue = asyncio.Queue(maxsize=1000)
        self.status = "disabled" if not settings.n8n_webhook_url else "connecting"
        self.failures = 0
        self.dropped = 0
        self.last_success = None
        self.task = None
        self.pending_records = []

    def emit(
        self,
        event_type,
        symbol="",
        source="system",
        venue="",
        severity="info",
        metadata=None,
    ):
        event = dict(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=now_ms(),
            symbol=symbol,
            source=source,
            venue=venue,
            severity=severity,
            metadata=metadata or {},
            component="quant-engine",
            action=event_type,
            result=(metadata or {}).get("status", "recorded"),
            reason=(metadata or {}).get("reason", ""),
        )
        self.events.appendleft(event)
        self.pending_records.append(
            record(
                "audit_event",
                event["event_id"],
                event,
                timestamp=event["timestamp"],
                symbol=symbol,
                exchange=venue,
            )
        )
        if len(self.pending_records) > 5000:
            self.pending_records = self.pending_records[-5000:]
            self.dropped += 1
        # Only meaningful lifecycle events. Never dispatch quotes/ticks.
        if self.settings.n8n_webhook_url and event_type in {
            "HIGH_CONFIDENCE_OPPORTUNITY",
            "SUBSCRIPTION_UPDATED",
            "OPPORTUNITY_EXPIRED",
            "PAPER_TRADE_EXECUTED",
            "PAPER_TRADE_REJECTED",
            "MARKET_DISCONNECTED",
            "MARKET_DATA_STALE",
            "SYSTEM_ERROR",
        }:
            try:
                self.queue.put_nowait(event)
            except asyncio.QueueFull:
                self.dropped += 1
        return event

    async def start(self):
        configs = await self.repository.list("automation_config", 1)
        if configs:
            self.config = AutomationConfig(**configs[0])
            # Process restarts always disarm automated trading.
            self.config.auto_paper_trade = False
        self.task = asyncio.create_task(self.worker())

    async def worker(self):
        async with httpx.AsyncClient(timeout=3) as client:
            while True:
                try:
                    if self.pending_records:
                        batch = self.pending_records[:200]
                        await self.repository.put_many(batch)
                        del self.pending_records[: len(batch)]
                    try:
                        event = await asyncio.wait_for(self.queue.get(), timeout=1)
                    except asyncio.TimeoutError:
                        continue
                    for attempt in range(3):
                        try:
                            response = await client.post(
                                self.settings.n8n_webhook_url,
                                json=event,
                                headers={
                                    "X-Automation-Token": self.settings.automation_token
                                },
                            )
                            response.raise_for_status()
                            self.status = "connected"
                            self.last_success = now_ms()
                            break
                        except (httpx.HTTPError, OSError) as exc:
                            self.failures += 1
                            self.status = "disconnected"
                            logging.warning(
                                json.dumps(
                                    {
                                        "event": "n8n_delivery_failed",
                                        "event_id": event["event_id"],
                                        "attempt": attempt + 1,
                                        "error": str(exc),
                                    }
                                )
                            )
                            await asyncio.sleep(0.5 * 2**attempt)
                    else:
                        await self.repository.put_many(
                            [
                                record(
                                    "automation_dead_letter",
                                    event["event_id"],
                                    event,
                                    status="failed",
                                )
                            ]
                        )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logging.exception("Automation worker failure; scanner unaffected")
                    await asyncio.sleep(1)

    async def configure(self, config):
        await self.repository.put_many(
            [record("automation_config", "current", config.model_dump())]
        )
        self.config = config
        self.emit(
            "CONFIGURATION_CHANGED",
            metadata={"auto_paper_trade": config.auto_paper_trade},
        )
        return self.snapshot()

    def snapshot(self):
        return {
            "n8n": self.status,
            "last_success": self.last_success,
            "delivery_failures": self.failures,
            "queued": self.queue.qsize(),
            "dropped": self.dropped,
            "config": self.config.model_dump(),
            "events": list(self.events)[:100],
            "notifications": {
                "local": "enabled",
                "external": "optional n8n credential configuration",
            },
        }

    async def stop(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.pending_records:
            try:
                await self.repository.put_many(self.pending_records)
            except Exception:
                logging.exception("Audit flush failed during shutdown")


class OpportunityLifecycle:
    def __init__(self, bus):
        self.bus = bus
        self.active = {}
        self.history = deque(maxlen=1000)
        self.detected = 0
        self.expired = 0

    def update(self, opportunities):
        current = {o.id: o for o in opportunities}
        for key, op in current.items():
            payload = op.model_dump()
            if key not in self.active:
                self.detected += 1
                payload.update(
                    status="ACTIVE",
                    detected_at=op.first_seen,
                    expired_at=None,
                    rejection_reason=None,
                    lifecycle=[
                        {"status": s, "timestamp": now_ms()}
                        for s in ["DETECTED", "VALIDATING", "QUALIFIED", "ACTIVE"]
                    ],
                )
                for event in ["OPPORTUNITY_DETECTED", "OPPORTUNITY_VALIDATED"]:
                    self.bus.emit(
                        event, op.symbol, op.source, op.buy_venue, metadata=payload
                    )
                cfg = self.bus.config
                if (
                    (cfg.high_confidence_alerts or cfg.auto_paper_trade)
                    and op.net_edge_percent >= cfg.min_auto_edge
                    and op.confidence_score >= cfg.min_auto_confidence
                    and op.liquidity_score >= cfg.min_liquidity
                ):
                    self.bus.emit(
                        "HIGH_CONFIDENCE_OPPORTUNITY",
                        "SUBSCRIPTION_UPDATED",
                        op.symbol,
                        op.source,
                        op.buy_venue,
                        metadata=payload,
                    )
            else:
                prior = self.active[key]
                payload.update(
                    status=prior["status"],
                    detected_at=prior["detected_at"],
                    expired_at=None,
                    rejection_reason=None,
                    lifecycle=prior["lifecycle"],
                )
            self.active[key] = payload
        for key in list(self.active):
            if key not in current:
                payload = self.active.pop(key)
                payload.update(status="EXPIRED", expired_at=now_ms())
                payload["lifecycle"].append(
                    {"status": "EXPIRED", "timestamp": now_ms()}
                )
                self.history.appendleft(payload)
                self.expired += 1
                self.bus.emit(
                    "OPPORTUNITY_EXPIRED",
                    payload["symbol"],
                    payload["source"],
                    payload["buy_venue"],
                    metadata=payload,
                )

    def executed(self, op_id):
        if op_id in self.active:
            self.active[op_id]["status"] = "EXECUTED"
            self.active[op_id]["lifecycle"].append(
                {"status": "EXECUTED", "timestamp": now_ms()}
            )
