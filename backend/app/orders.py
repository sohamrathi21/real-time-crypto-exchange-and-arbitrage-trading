import asyncio
import copy
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from .models import now_ms
from .storage import record


class OrderRequest(BaseModel):
    symbol: str
    venue: str
    side: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT"]
    quantity: float = Field(gt=0, allow_inf_nan=False)
    requested_price: float | None = Field(None, gt=0, allow_inf_nan=False)
    idempotency_key: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def check_limit(self):
        if self.order_type == "LIMIT" and self.requested_price is None:
            raise ValueError("Limit price is required")
        return self


class BrokerAdapter(ABC):
    @abstractmethod
    def match(self, book, side, quantity, limit, consumed):
        """Implementations here must only return simulated fills."""


class PaperBrokerAdapter(BrokerAdapter):
    def match(self, book, side, quantity, limit, consumed):
        levels = book.asks if side == "BUY" else book.bids
        remaining = quantity
        fills = []
        for level in levels:
            if limit is not None and (
                (side == "BUY" and level.price > limit)
                or (side == "SELL" and level.price < limit)
            ):
                break
            available = max(0, level.quantity - consumed.get(str(level.price), 0))
            take = min(remaining, available)
            if take > 1e-12:
                fills.append({"price": level.price, "quantity": take})
                remaining -= take
            if remaining < quantity * 1e-10:
                break
        return fills


class OrderEngine:
    """Long-only, per-venue paper positions; no real broker or order endpoints."""

    def __init__(self, settings, repository, paper, bus):
        self.settings, self.repository, self.paper, self.bus = (
            settings,
            repository,
            paper,
            bus,
        )
        self.lock = paper.lock
        self.orders = {}
        self.positions = {}
        self.cash_delta = {}
        self.realized = {}
        self.fees = {}
        self.peaks = {}
        self.consumed = {}
        self.adapter = PaperBrokerAdapter()
        self.task = None

    async def load(self):
        records = await self.repository.list("execution_state", 1)
        if records:
            for key in [
                "orders",
                "positions",
                "cash_delta",
                "realized",
                "fees",
                "peaks",
            ]:
                setattr(self, key, records[0].get(key, {}))
            # Open orders expire on restart: old reservations never silently execute.
            for order in self.orders.values():
                if order["status"] in ["OPEN", "PARTIALLY_FILLED", "SUBMITTED"]:
                    self.transition(
                        order,
                        "EXPIRED",
                        "Engine restarted; resubmit against current books",
                    )

    def state(self):
        return {
            k: getattr(self, k)
            for k in ["orders", "positions", "cash_delta", "realized", "fees", "peaks"]
        }

    async def persist(self):
        await self.repository.put_many(
            [record("execution_state", "current", self.state())]
        )

    def transition(self, order, status, reason=""):
        order["status"] = status
        order["history"].append(
            {"timestamp": now_ms(), "status": status, "reason": reason}
        )
        order["reason"] = reason
        self.bus.emit(
            "ORDER_" + status,
            order["symbol"],
            order["source"],
            order["venue"],
            metadata={
                "order_id": order["order_id"],
                "status": status,
                "reason": reason,
            },
        )

    def position_key(self, venue, symbol, source):
        return f"{venue}:{symbol}:{source}"

    def reserved(self, quote, exclude=None):
        return sum(
            o["remaining_quantity"] * o["reserve_price"] * (1 + o["fee_rate"])
            for o in self.orders.values()
            if o["order_id"] != exclude
            and o["quote"] == quote
            and o["side"] == "BUY"
            and o["status"] in ["OPEN", "PARTIALLY_FILLED", "SUBMITTED"]
        )

    def portfolio(self, books, quote="USDT"):
        base = self.paper.portfolio(quote)
        cash = base["available_capital"] + self.cash_delta.get(quote, 0)
        positions = []
        market_value = unrealized = 0
        for p in self.positions.values():
            if p["quote"] != quote or p["quantity"] <= 1e-12:
                continue
            b = books.get((p["venue"], p["symbol"]))
            valid = (
                b is not None
                and b.source == p["source"]
                and now_ms() - b.timestamp <= self.settings.max_price_age_ms
            )
            mark = b.bids[0].price if valid else p["average_entry"]
            value = p["quantity"] * mark
            upl = value - p["quantity"] * p["average_entry"]
            market_value += value
            unrealized += upl
            positions.append(
                {
                    **p,
                    "mark_price": mark,
                    "market_value": value,
                    "unrealized_pnl": upl,
                    "stale": not valid,
                }
            )
        equity = cash + market_value
        self.peaks[quote] = max(
            self.peaks.get(quote, self.settings.starting_capital), equity
        )
        return {
            **base,
            "available_cash": cash - self.reserved(quote),
            "reserved_cash": self.reserved(quote),
            "portfolio_value": equity,
            "exposure": market_value,
            "unrealized_pnl": unrealized,
            "realized_pnl": base["realized_pnl"] + self.realized.get(quote, 0),
            "fees": self.fees.get(quote, 0),
            "net_pnl": equity - self.settings.starting_capital,
            "positions": positions,
            "today_realized_pnl": sum(
                t["net_profit"]
                for t in self.paper.trades
                if t["quote"] == quote
                and datetime.fromtimestamp(t["timestamp"] / 1000, timezone.utc).date()
                == datetime.now(timezone.utc).date()
            )
            + sum(
                o.get("realized_pnl", 0)
                for o in self.orders.values()
                if o["quote"] == quote
                and datetime.fromtimestamp(o["created_at"] / 1000, timezone.utc).date()
                == datetime.now(timezone.utc).date()
            ),
            "drawdown_percent": (self.peaks[quote] - equity) / self.peaks[quote] * 100,
            "accounting": "Long-only paper positions, valued at bid. Buy fees included in cost basis. Quote currencies never combined.",
        }

    def validation(self, request, book, scanner):
        if now_ms() - book.timestamp > self.settings.max_price_age_ms:
            raise ValueError("Stale order book")
        if not book.market_open:
            raise ValueError("Market is closed")
        if book.latency_ms > self.settings.max_latency_ms:
            raise ValueError("Provider latency exceeds limit")
        reference = book.asks[0].price if request.side == "BUY" else book.bids[0].price
        capital = request.quantity * (request.requested_price or reference)
        depth = sum(
            l.price * l.quantity
            for l in (book.asks if request.side == "BUY" else book.bids)
        )
        if min(100, depth / max(capital, 1e-12) * 10) < self.settings.min_liquidity:
            raise ValueError("Minimum liquidity score not met")
        if capital > self.settings.max_trade_size:
            raise ValueError("Maximum trade capital exceeded")
        if capital > self.settings.max_position_notional:
            raise ValueError("Maximum position size exceeded")
        today = datetime.now(timezone.utc).date()
        daily = sum(
            datetime.fromtimestamp(o["created_at"] / 1000, timezone.utc).date() == today
            and o["status"] != "REJECTED"
            for o in self.orders.values()
        ) + sum(
            datetime.fromtimestamp(t["timestamp"] / 1000, timezone.utc).date() == today
            for t in self.paper.trades
        )
        if daily >= self.settings.max_daily_paper_trades:
            raise ValueError("Maximum daily paper orders reached")
        account = self.portfolio(scanner.cache.books, book.quote)
        if account["drawdown_percent"] >= self.settings.max_drawdown_percent:
            raise ValueError("Maximum drawdown reached")
        key = self.position_key(book.exchange, book.symbol, book.source)
        position = self.positions.get(key, {"quantity": 0})
        if request.side == "BUY":
            if capital * (1 + book.fee_rate) > account["available_cash"]:
                raise ValueError("Insufficient available cash after reservations")
            if (
                position["quantity"] + request.quantity
            ) * reference > self.settings.max_position_notional:
                raise ValueError("Maximum aggregate position size exceeded")
        else:
            reserved = sum(
                o["remaining_quantity"]
                for o in self.orders.values()
                if o["symbol"] == book.symbol
                and o["venue"] == book.exchange
                and o["source"] == book.source
                and o["side"] == "SELL"
                and o["status"] in ["OPEN", "PARTIALLY_FILLED"]
            )
            if request.quantity > position["quantity"] - reserved + 1e-10:
                raise ValueError(
                    "Insufficient unreserved inventory; short selling is disabled"
                )

    async def submit(self, request, scanner):
        async with self.lock:
            prior = next(
                (
                    o
                    for o in self.orders.values()
                    if o["idempotency_key"] == request.idempotency_key
                ),
                None,
            )
            if prior:
                if prior["request"] != request.model_dump():
                    raise ValueError("Idempotency key belongs to a different order")
                return prior
            async with scanner.lock:
                book = scanner.cache.books.get((request.venue, request.symbol))
                if not book:
                    raise ValueError("Order book unavailable")
                order = {
                    **request.model_dump(),
                    "order_id": str(uuid.uuid4()),
                    "request": request.model_dump(),
                    "source": book.source,
                    "quote": book.quote,
                    "average_fill_price": 0,
                    "filled_quantity": 0,
                    "remaining_quantity": request.quantity,
                    "fees": 0,
                    "slippage": 0,
                    "price_impact": 0,
                    "created_at": now_ms(),
                    "filled_at": None,
                    "latency_ms": 0,
                    "history": [],
                    "fills": [],
                    "fee_rate": book.fee_rate,
                    "reserve_price": request.requested_price or book.asks[0].price,
                    "expires_at": now_ms() + 86400000,
                    "ready_at": now_ms() + self.settings.execution_delay_ms,
                }
                self.transition(order, "CREATED")
                self.transition(order, "VALIDATING")
                try:
                    self.validation(request, book, scanner)
                except ValueError as exc:
                    self.transition(order, "REJECTED", str(exc))
                    self.orders[order["order_id"]] = order
                    await self.persist()
                    return order
                self.transition(order, "SUBMITTED")
                self.transition(order, "OPEN")
                self.orders[order["order_id"]] = order
                try:
                    await self.persist()
                except Exception:
                    self.orders.pop(order["order_id"], None)
                    raise
                return order

    async def cancel(self, identifier):
        async with self.lock:
            order = self.orders.get(identifier)
            if not order:
                raise ValueError("Order not found")
            if order["status"] not in ["OPEN", "PARTIALLY_FILLED", "SUBMITTED"]:
                raise ValueError("Only open orders can be cancelled")
            previous = copy.deepcopy(order)
            self.transition(order, "CANCELLED", "Cancelled by user")
            try:
                await self.persist()
            except Exception:
                self.orders[identifier] = previous
                raise
            return order

    async def process(self, scanner):
        async with self.lock:
            async with scanner.lock:
                before = copy.deepcopy(self.state())
                used_before = copy.deepcopy(self.consumed)
                changed = False
                active_versions = {
                    f"{b.exchange}:{b.symbol}:{b.source}:{b.sequence}"
                    for b in scanner.cache.books.values()
                }
                self.consumed = {
                    k: v
                    for k, v in self.consumed.items()
                    if k.rsplit(":", 1)[0] in active_versions
                }
                for order in list(self.orders.values()):
                    if (
                        order["status"] not in ["OPEN", "PARTIALLY_FILLED"]
                        or now_ms() < order["ready_at"]
                    ):
                        continue
                    if now_ms() > order["expires_at"]:
                        self.transition(
                            order, "EXPIRED", "Paper order time to live exceeded"
                        )
                        changed = True
                        continue
                    book = scanner.cache.books.get((order["venue"], order["symbol"]))
                    if (
                        not book
                        or book.source != order["source"]
                        or now_ms() - book.timestamp > self.settings.max_price_age_ms
                        or not book.market_open
                    ):
                        if order["order_type"] == "MARKET":
                            self.transition(
                                order,
                                "REJECTED",
                                "Market data became stale or source changed",
                            )
                            changed = True
                        continue
                    version = (
                        f"{book.exchange}:{book.symbol}:{book.source}:{book.sequence}"
                    )
                    # Arbitrage executions reserve the whole displayed snapshot conservatively.
                    if any(
                        version in t.get("book_versions", [])
                        for t in self.paper.trades[-5000:]
                    ):
                        continue
                    consume_key = version + ":" + order["side"]
                    consumed = self.consumed.setdefault(consume_key, {})
                    fills = self.adapter.match(
                        book,
                        order["side"],
                        order["remaining_quantity"],
                        order["requested_price"],
                        consumed,
                    )
                    if not fills:
                        if order["order_type"] == "MARKET":
                            self.transition(
                                order, "CANCELLED", "No remaining displayed liquidity"
                            )
                            changed = True
                        continue
                    qty = sum(f["quantity"] for f in fills)
                    notional = sum(f["quantity"] * f["price"] for f in fills)
                    reference = (
                        book.asks[0].price
                        if order["side"] == "BUY"
                        else book.bids[0].price
                    )
                    impact = abs(notional / qty - reference) * qty
                    if impact / notional * 100 > self.settings.max_slippage_percent:
                        self.transition(
                            order, "REJECTED", "Slippage limit exceeded before fill"
                        )
                        changed = True
                        continue
                    fee = notional * book.fee_rate
                    quote = book.quote
                    key = self.position_key(book.exchange, book.symbol, book.source)
                    position = self.positions.setdefault(
                        key,
                        {
                            "symbol": book.symbol,
                            "venue": book.exchange,
                            "source": book.source,
                            "quote": quote,
                            "quantity": 0.0,
                            "average_entry": 0.0,
                            "realized_pnl": 0.0,
                        },
                    )
                    if order["side"] == "BUY":
                        cash = (
                            self.paper.portfolio(quote)["available_capital"]
                            + self.cash_delta.get(quote, 0)
                            - self.reserved(quote, order["order_id"])
                        )
                        if (
                            notional + fee > cash
                            or (position["quantity"] + qty) * reference
                            > self.settings.max_position_notional
                        ):
                            self.transition(
                                order,
                                "REJECTED",
                                "Cash or position limit changed before execution",
                            )
                            changed = True
                            continue
                        position["average_entry"] = (
                            position["average_entry"] * position["quantity"]
                            + notional
                            + fee
                        ) / (position["quantity"] + qty)
                        position["quantity"] += qty
                        self.cash_delta[quote] = (
                            self.cash_delta.get(quote, 0) - notional - fee
                        )
                    else:
                        if qty > position["quantity"] + 1e-10:
                            self.transition(
                                order,
                                "REJECTED",
                                "Inventory unavailable before execution",
                            )
                            changed = True
                            continue
                        realized = notional - fee - position["average_entry"] * qty
                        position["quantity"] -= qty
                        position["realized_pnl"] += realized
                        order["realized_pnl"] = order.get("realized_pnl", 0) + realized
                        self.realized[quote] = self.realized.get(quote, 0) + realized
                        self.cash_delta[quote] = (
                            self.cash_delta.get(quote, 0) + notional - fee
                        )
                    self.fees[quote] = self.fees.get(quote, 0) + fee
                    oldfilled = order["filled_quantity"]
                    order["filled_quantity"] += qty
                    order["average_fill_price"] = (
                        order["average_fill_price"] * oldfilled + notional
                    ) / order["filled_quantity"]
                    order["remaining_quantity"] = max(
                        0, order["quantity"] - order["filled_quantity"]
                    )
                    order["fees"] += fee
                    order["price_impact"] += impact
                    order["slippage"] += impact
                    order["latency_ms"] = now_ms() - order["created_at"]
                    for fill in fills:
                        consumed[str(fill["price"])] = (
                            consumed.get(str(fill["price"]), 0) + fill["quantity"]
                        )
                        order["fills"].append(
                            {**fill, "timestamp": now_ms(), "simulated": True}
                        )
                    if order["remaining_quantity"] <= order["quantity"] * 1e-8:
                        order["filled_at"] = now_ms()
                        self.transition(order, "FILLED")
                    else:
                        self.transition(order, "PARTIALLY_FILLED")
                        if order["order_type"] == "MARKET":
                            self.transition(
                                order,
                                "CANCELLED",
                                "IOC remainder cancelled; displayed depth exhausted",
                            )
                    changed = True
                if changed:
                    try:
                        await self.persist()
                    except Exception:
                        for key, value in before.items():
                            setattr(self, key, value)
                        self.consumed = used_before
                        raise

    async def run(self, scanner):
        while True:
            try:
                await self.process(scanner)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.bus.emit(
                    "SYSTEM_ERROR",
                    severity="error",
                    metadata={
                        "reason": "Paper fill persistence failed: " + str(exc)[:100]
                    },
                )
            await asyncio.sleep(0.2)

    def snapshot(self, books):
        return {
            "orders": sorted(
                self.orders.values(), key=lambda o: o["created_at"], reverse=True
            )[:200],
            "account": self.portfolio(books),
            "assumptions": [
                "Paper only; long-only positions. No exchange queue priority.",
                "Limit orders fill only against marketable displayed levels; market orders use IOC remainder cancellation.",
                "Displayed liquidity is shared between paper orders per snapshot. Subsequent snapshots may replenish depth.",
                "Manual orders do not require positive arbitrage edge; arbitrage risk thresholds apply to paired routes.",
            ],
        }
