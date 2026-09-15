import asyncio
import copy
import time
import uuid
from datetime import datetime, timezone
from .analytics import portfolio_stats
from .models import now_ms
from .storage import record


class PaperEngine:
    def __init__(self, repository, settings):
        self.repository = repository
        self.settings = settings
        self.trades = []
        self.lock = asyncio.Lock()
        self.executed_snapshots = set()
        self.order_engine = None

    async def load(self):
        self.trades = list(reversed(await self.repository.list("paper_trade", 1000000)))
        self.executed_snapshots = {t["snapshot_key"] for t in self.trades}

    def portfolio(self, quote="USDT"):
        result = portfolio_stats(
            [t for t in self.trades if t["quote"] == quote],
            self.settings.starting_capital,
        )
        result["quote"] = quote
        return result

    async def execute(self, request, scanner, automated=False):
        async with self.lock:
            prior = next(
                (
                    t
                    for t in self.trades
                    if t["idempotency_key"] == request.idempotency_key
                ),
                None,
            )
            if prior:
                if (
                    prior["opportunity_id"] != request.opportunity_id
                    or prior.get("execution_scenario", "normal")
                    != request.execution_scenario
                ):
                    raise ValueError("Idempotency key belongs to a different execution")
                return prior
            start = time.perf_counter()
            submitted = now_ms()
            scanner.bus.emit(
                "ARBITRAGE_SUBMITTED",
                metadata={"opportunity_id": request.opportunity_id},
            )
            await asyncio.sleep(self.settings.execution_delay_ms / 1000)
            # The feed keeps running during delay; final validation uses new books.
            async with scanner.lock:
                fresh = scanner.detector.scan(list(scanner.cache.books.values()))
                op = next((o for o in fresh if o.id == request.opportunity_id), None)
                if not op:
                    raise ValueError(
                        "Opportunity expired or no longer passes risk filters"
                    )
                if request.execution_scenario != "normal" and (
                    op.source != "demo" or automated
                ):
                    raise ValueError(
                        "Failure scenarios are available only for manual demo executions"
                    )
                if request.execution_scenario == "price_moved":
                    raise ValueError(
                        "DEMO SCENARIO: opportunity no longer profitable after simulated adverse move"
                    )
                if (
                    request.execution_scenario == "partial_sell"
                    and op.type == "triangular"
                ):
                    raise ValueError(
                        "Partial sell scenario requires a cross-exchange route"
                    )
                cfg = scanner.bus.config
                today = datetime.now(timezone.utc).date()
                daily = sum(
                    datetime.fromtimestamp(t["timestamp"] / 1000, timezone.utc).date()
                    == today
                    for t in self.trades
                )
                if self.order_engine:
                    daily += sum(
                        datetime.fromtimestamp(
                            o["created_at"] / 1000, timezone.utc
                        ).date()
                        == today
                        and o["status"] != "REJECTED"
                        for o in self.order_engine.orders.values()
                    )
                if daily >= self.settings.max_daily_paper_trades:
                    raise ValueError("Maximum daily paper trades reached")
                if automated:
                    if not cfg.auto_paper_trade:
                        raise ValueError(
                            "Auto paper trading is OFF (kill switch or disabled)"
                        )
                    if daily >= cfg.max_daily_paper_trades:
                        raise ValueError("Automation daily limit reached")
                    if (
                        op.net_edge_percent < cfg.min_auto_edge
                        or op.confidence_score < cfg.min_auto_confidence
                        or op.capital_required > cfg.max_auto_capital
                        or op.liquidity_score < cfg.min_liquidity
                    ):
                        raise ValueError(
                            "Opportunity fails final automation thresholds"
                        )
                keys = (
                    [(op.buy_venue, op.symbol), (op.sell_venue, op.symbol)]
                    if op.type != "triangular"
                    else [(op.buy_venue, leg["symbol"]) for leg in op.legs]
                )
                snapshot_key = "|".join(
                    f"{v}:{s}:{scanner.cache.books[(v,s)].sequence}" for v, s in keys
                )
                versions = [
                    f"{v}:{s}:{scanner.cache.books[(v,s)].source}:{scanner.cache.books[(v,s)].sequence}"
                    for v, s in keys
                ]
                used_books = (
                    set().union(
                        *(set(t.get("book_versions", [])) for t in self.trades[-5000:])
                    )
                    if self.trades
                    else set()
                )
                if self.order_engine:
                    used_books.update(
                        key.rsplit(":", 1)[0]
                        for key, consumed in self.order_engine.consumed.items()
                        if consumed
                    )
                if any(v in used_books for v in versions):
                    raise ValueError(
                        "This order-book snapshot was already consumed; wait for the next update"
                    )
                portfolio = (
                    self.order_engine.portfolio(scanner.cache.books, op.quote)
                    if self.order_engine
                    else self.portfolio(op.quote)
                )
                if op.capital_required > portfolio.get(
                    "available_cash", portfolio["available_capital"]
                ):
                    raise ValueError(
                        "Insufficient simulated capital after open-order reservations"
                    )
                if (
                    portfolio.get(
                        "drawdown_percent", portfolio.get("maximum_drawdown", 0)
                    )
                    >= self.settings.max_drawdown_percent
                ):
                    raise ValueError("Maximum drawdown reached")
                fraction = 0.6 if request.execution_scenario == "partial_sell" else 1
                trade = {
                    **op.model_dump(),
                    "id": str(uuid.uuid4()),
                    "opportunity_id": op.id,
                    "idempotency_key": request.idempotency_key,
                    "snapshot_key": snapshot_key,
                    "book_versions": versions,
                    "timestamp": now_ms(),
                    "status": "simulated" if fraction == 1 else "partial_exposure",
                    "entry_price": op.buy_price,
                    "exit_price": op.sell_price,
                    "fees": op.buy_fee + op.sell_fee,
                    "latency_ms": (time.perf_counter() - start) * 1000,
                    "execution_scenario": request.execution_scenario,
                    "origin": "automated" if automated else "manual",
                    "expected_profit": op.net_profit,
                    "execution_history": [
                        {"status": "SUBMITTED", "timestamp": submitted},
                        {"status": "VALIDATING", "timestamp": now_ms()},
                    ],
                    "execution_legs": [],
                    "remaining_exposure": 0,
                }
                oldstate = (
                    copy.deepcopy(self.order_engine.state())
                    if self.order_engine
                    else None
                )
                if fraction < 1:
                    if not self.order_engine:
                        raise ValueError(
                            "Position engine required for partial execution"
                        )
                    remaining = op.trade_quantity * (1 - fraction)
                    cost = op.buy_price * remaining + op.buy_fee * (1 - fraction)
                    key = self.order_engine.position_key(
                        op.buy_venue, op.symbol, op.source
                    )
                    position = self.order_engine.positions.setdefault(
                        key,
                        {
                            "symbol": op.symbol,
                            "venue": op.buy_venue,
                            "source": op.source,
                            "quote": op.quote,
                            "quantity": 0.0,
                            "average_entry": 0.0,
                            "realized_pnl": 0.0,
                        },
                    )
                    if (
                        position["quantity"] + remaining
                    ) * op.buy_price > self.settings.max_position_notional:
                        raise ValueError("Partial-fill exposure exceeds position cap")
                    position["average_entry"] = (
                        position["average_entry"] * position["quantity"] + cost
                    ) / (position["quantity"] + remaining)
                    position["quantity"] += remaining
                    self.order_engine.cash_delta[op.quote] = (
                        self.order_engine.cash_delta.get(op.quote, 0) - cost
                    )
                    trade["gross_profit"] = op.gross_profit * fraction
                    trade["buy_fee"] = op.buy_fee * fraction
                    trade["sell_fee"] = op.sell_fee * fraction
                    trade["capitalized_buy_fee"] = op.buy_fee * (1 - fraction)
                    trade["estimated_slippage"] = op.estimated_slippage * (
                        0.5 + 0.5 * fraction
                    )
                    trade["fees"] = op.buy_fee + op.sell_fee * fraction
                    trade["net_profit"] = (
                        trade["gross_profit"]
                        - trade["buy_fee"]
                        - trade["sell_fee"]
                        - trade["estimated_slippage"]
                        - op.other_costs
                    )
                    trade["roi"] = trade["net_profit"] / op.capital_required * 100
                    trade["remaining_exposure"] = remaining
                if op.type == "triangular":
                    trade["execution_legs"] = [
                        {**leg, "status": "FILLED", "timestamp": now_ms()}
                        for leg in op.legs
                    ]
                else:
                    trade["execution_legs"] = [
                        {
                            "venue": op.buy_venue,
                            "side": "BUY",
                            "quantity": op.trade_quantity,
                            "vwap": op.buy_price,
                            "status": "FILLED",
                            "timestamp": now_ms(),
                        },
                        {
                            "venue": op.sell_venue,
                            "side": "SELL",
                            "quantity": op.trade_quantity * fraction,
                            "vwap": op.sell_price,
                            "status": "FILLED" if fraction == 1 else "PARTIALLY_FILLED",
                            "timestamp": now_ms(),
                        },
                    ]
                trade["execution_history"].append(
                    {
                        "status": "COMPLETE" if fraction == 1 else "PARTIAL_EXPOSURE",
                        "timestamp": now_ms(),
                    }
                )
                updated = portfolio_stats(
                    [t for t in self.trades if t["quote"] == op.quote] + [trade],
                    self.settings.starting_capital,
                )
                records = [
                    record(
                        "paper_trade",
                        trade["id"],
                        trade,
                        opportunity_id=op.id,
                        symbol=op.symbol,
                        exchange=op.buy_venue,
                        net_edge=op.net_edge_percent,
                        status=trade["status"],
                    ),
                    record("portfolio", op.quote, updated),
                ]
                if self.order_engine:
                    records.append(
                        record("execution_state", "current", self.order_engine.state())
                    )
                try:
                    await self.repository.put_many(records)
                except Exception:
                    if self.order_engine and oldstate:
                        for k, v in oldstate.items():
                            setattr(self.order_engine, k, v)
                    raise
                self.trades.append(trade)
                self.executed_snapshots.add(snapshot_key)
                for leg in trade["execution_legs"]:
                    scanner.bus.emit(
                        "ARBITRAGE_LEG_" + leg["status"],
                        op.symbol,
                        op.source,
                        metadata=leg,
                    )
                scanner.lifecycle.executed(op.id)
                return trade
