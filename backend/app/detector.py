from collections import defaultdict
from .models import Opportunity, now_ms
from .orderbook import sweep, buy_with_budget, InsufficientLiquidity
from .analytics import confidence
from .graph import triangular_cycles
from .risk import rejection_reasons


class Detector:
    def __init__(self, settings):
        self.settings = settings
        self.first_seen = {}
        self.rejected = 0
        self.volatility = {}
        self.reliability = {}

    def metrics(self, identifier, books, edge, liquidity, slippage, at):
        first = self.first_seen.setdefault(identifier, at)
        age = max(at - b.timestamp for b in books)
        latency = sum(b.latency_ms for b in books)
        score, factors = confidence(
            edge=edge,
            liquidity=liquidity,
            depth=min(min(len(b.bids), len(b.asks)) for b in books),
            age=age,
            latency=latency,
            duration=(at - first) / 1000,
            slippage=slippage,
            volatility=max(self.volatility.get(b.symbol, 0) for b in books),
            reliability=min(self.reliability.get(b.exchange, 1) for b in books),
            settings=self.settings,
        )
        return dict(
            confidence_score=score,
            confidence_factors=factors,
            timestamp=at,
            first_seen=first,
            price_age_ms=age,
            execution_latency=latency,
        )

    def cross(self, buy, sell, at):
        if buy.quote not in ("USDT", "USD", "INR"):
            return None  # TRADE_NOTIONAL is denominated in cash/stablecoin units, never BTC.
        if buy.exchange == sell.exchange or not buy.market_open or not sell.market_open:
            return None
        if (
            buy.symbol,
            buy.source,
            buy.instrument_id,
            buy.settlement,
            buy.asset_class,
        ) != (
            sell.symbol,
            sell.source,
            sell.instrument_id,
            sell.settlement,
            sell.asset_class,
        ):
            return None
        if not buy.instrument_id or sell.bids[0].price <= buy.asks[0].price:
            return None
        size = self.settings.trade_notional / buy.asks[0].price
        a, b = sweep(buy.asks, size), sweep(sell.bids, size)
        buy_fee, sell_fee = a.notional * buy.fee_rate, b.notional * sell.fee_rate
        gross = b.notional - a.notional
        # VWAP already includes book impact. Charge ONLY residual uncertainty again.
        residual = (
            (a.notional + b.notional) * self.settings.residual_slippage_bps / 10000
        )
        impact = a.impact + b.impact
        net = gross - buy_fee - sell_fee - residual - self.settings.other_cost
        # Include marked value of inventory prepositioned at the sell venue.
        capital = a.notional + buy_fee + b.notional
        edge = net / capital * 100
        liquidity = min(
            sum(x.price * x.quantity for x in buy.asks),
            sum(x.price * x.quantity for x in sell.bids),
        )
        liquidity_score = min(100, liquidity / (a.notional * 10) * 100)
        slippage = (residual + impact) / (a.notional + b.notional) * 100
        identifier = f"cross:{buy.exchange}:{sell.exchange}:{buy.symbol}:{buy.source}"
        return Opportunity(
            id=identifier,
            symbol=buy.symbol,
            type="cross_venue" if buy.asset_class == "equity" else "cross_exchange",
            buy_venue=buy.exchange,
            sell_venue=sell.exchange,
            source=buy.source,
            quote=buy.quote,
            buy_price=a.vwap,
            sell_price=b.vwap,
            trade_quantity=size,
            gross_profit=gross,
            buy_fee=buy_fee,
            sell_fee=sell_fee,
            estimated_slippage=residual,
            price_impact=impact,
            slippage_percent=slippage,
            other_costs=self.settings.other_cost,
            net_profit=net,
            gross_spread_percent=(b.vwap / a.vwap - 1) * 100,
            net_edge_percent=edge,
            capital_required=capital,
            roi=edge,
            liquidity_score=liquidity_score,
            available_liquidity=liquidity,
            assumptions=[
                "Prefunded buy cash and sell inventory; capital includes both legs.",
                "No transfer on critical path; network cost zero. Rebalancing costs excluded.",
                "VWAP depth impact included in execution prices; residual slippage charged separately.",
                "Fee rates are configurable estimates, not account-specific quotes.",
            ],
            **self.metrics(
                identifier, [buy, sell], edge, liquidity_score, slippage, at
            ),
        )

    def triangle(self, edges, at):
        budget = self.settings.trade_notional

        def replay(fee_count):
            amount, legs, impact_total = budget, [], 0.0
            for index, e in enumerate(edges):
                fill = (
                    buy_with_budget(e.book.asks, amount)
                    if e.side == "buy"
                    else sweep(e.book.bids, amount)
                )
                output = fill.quantity if e.side == "buy" else fill.notional
                fee = output * e.book.fee_rate if index < fee_count else 0
                legs.append(
                    dict(
                        symbol=e.book.symbol,
                        side=e.side,
                        input=amount,
                        output=output - fee,
                        fee=fee,
                        fee_currency=e.target,
                        vwap=fill.vwap,
                        quantity=fill.quantity,
                    )
                )
                # Quote-normalized impact estimate as proportion of each leg's notional.
                impact_total += fill.impact / fill.notional * budget
                amount = output - fee
            return amount, legs, impact_total

        raw, _, _ = replay(0)
        first, _, _ = replay(1)
        final, legs, impact = replay(3)
        fees = raw - final
        residual = budget * 3 * self.settings.residual_slippage_bps / 10000
        net = final - budget - residual - self.settings.other_cost
        edge = net / budget * 100
        slippage = (impact + residual) / budget * 100
        liquidity_ratios = []
        for e, leg in zip(edges, legs):
            capacity = (
                sum(l.price * l.quantity for l in e.book.asks)
                if e.side == "buy"
                else sum(l.quantity for l in e.book.bids)
            )
            liquidity_ratios.append(capacity / leg["input"])
        score = min(100, min(liquidity_ratios) * 10)
        path = [edges[0].source] + [e.target for e in edges]
        identifier = (
            f"tri:{edges[0].book.exchange}:{'-'.join(path)}:{edges[0].book.source}"
        )
        return Opportunity(
            id=identifier,
            symbol=" / ".join(path[:-1]),
            type="triangular",
            buy_venue=edges[0].book.exchange,
            sell_venue=edges[0].book.exchange,
            source=edges[0].book.source,
            quote=path[0],
            buy_price=1,
            sell_price=final / budget,
            trade_quantity=budget,
            gross_profit=raw - budget,
            buy_fee=raw - first,
            sell_fee=first - final,
            estimated_slippage=residual,
            price_impact=impact,
            slippage_percent=slippage,
            other_costs=self.settings.other_cost,
            net_profit=net,
            gross_spread_percent=(raw / budget - 1) * 100,
            net_edge_percent=edge,
            capital_required=budget,
            roi=edge,
            liquidity_score=score,
            available_liquidity=min(liquidity_ratios) * budget,
            path=path,
            legs=legs,
            assumptions=[
                "Three sequential depth-aware conversions; fees deducted from output at every leg.",
                "Fee drag measured in starting currency by fee-free vs fee-bearing replay.",
                "Atomic paper fills assumed; live leg risk and exchange rounding are not modeled.",
            ],
            **self.metrics(
                identifier, [e.book for e in edges], edge, score, slippage, at
            ),
        )

    def scan(self, books, at=None):
        at = at or now_ms()
        groups, venues = defaultdict(list), defaultdict(list)
        for b in books:
            if at - b.timestamp > self.settings.max_price_age_ms or not b.market_open:
                continue
            groups[(b.symbol, b.source, b.instrument_id)].append(b)
            venues[(b.exchange, b.source)].append(b)
        candidates = []
        self.rejected = 0
        for group in groups.values():
            for buy in group:
                for sell in group:
                    try:
                        op = self.cross(buy, sell, at)
                        if op:
                            candidates.append(op)
                    except InsufficientLiquidity:
                        self.rejected += 1
        for group in venues.values():
            for cycle in triangular_cycles(group):
                try:
                    candidates.append(self.triangle(cycle, at))
                except InsufficientLiquidity:
                    self.rejected += 1
        result = []
        for op in candidates:
            if rejection_reasons(op, self.settings):
                self.rejected += 1
            else:
                result.append(op)
        active = {op.id for op in result}
        self.first_seen = {k: v for k, v in self.first_seen.items() if k in active}
        return sorted(
            result, key=lambda o: (o.confidence_score, o.net_edge_percent), reverse=True
        )
