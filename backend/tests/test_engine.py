import asyncio
import math
import time
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from backend.app.models import Level, OrderBook, now_ms
from backend.app.orderbook import sweep, buy_with_budget, InsufficientLiquidity
from backend.app.config import Settings
from backend.app.detector import Detector
from backend.app.graph import Edge, has_negative_cycle, triangular_cycles
from backend.app.risk import rejection_reasons
from backend.app.providers.mock import MockProvider
from backend.app.main import create_app
from backend.app.cache import MarketCache
from backend.app.backtest import backtest


def book(venue="A", bid=99, ask=100, symbol="BTC/USDT", fee=0.001, qty=100):
    base, quote = symbol.split("/")
    return OrderBook(
        exchange=venue,
        symbol=symbol,
        base=base,
        quote=quote,
        bids=[Level(price=bid, quantity=qty)],
        asks=[Level(price=ask, quantity=qty)],
        timestamp=now_ms(),
        sequence="1",
        latency_ms=10,
        fee_rate=fee,
        instrument_id=symbol,
    )


def config(**kwargs):
    return Settings(
        min_confidence_score=0, min_liquidity=0, trade_notional=1000, **kwargs
    )


def test_vwap_partial_levels():
    fill = sweep([Level(price=100, quantity=2), Level(price=102, quantity=4)], 3)
    assert fill.notional == 302
    assert fill.vwap == pytest.approx(302 / 3)
    assert fill.impact == pytest.approx(2)
    with pytest.raises(InsufficientLiquidity):
        sweep([Level(price=100, quantity=2)], 3)
    with pytest.raises(ValueError):
        sweep([Level(price=100, quantity=2)], 0)


def test_budget_consumes_depth():
    fill = buy_with_budget(
        [Level(price=100, quantity=2), Level(price=102, quantity=4)], 302
    )
    assert fill.quantity == 3
    with pytest.raises(InsufficientLiquidity):
        buy_with_budget([Level(price=100, quantity=2)], 300)


@pytest.mark.parametrize("price", [0, -1, float("nan"), float("inf")])
def test_invalid_prices(price):
    with pytest.raises(ValidationError):
        Level(price=price, quantity=1)


def test_profit_fees_and_no_double_slippage():
    a, b = book(), book("B", bid=102, ask=103)
    op = Detector(config()).cross(a, b, now_ms())
    assert op.gross_profit == 20
    assert op.buy_fee == 1
    assert op.sell_fee == pytest.approx(1.02)
    assert op.estimated_slippage == pytest.approx(0.202)
    assert op.net_profit == pytest.approx(17.728)
    assert op.capital_required == 2021
    assert op.net_edge_percent == pytest.approx(op.net_profit / 2021 * 100)


def test_depth_impact_counted_once():
    a = book(qty=5)
    a.asks.append(Level(price=101, quantity=20))
    b = book("B", bid=104, ask=105)
    op = Detector(config()).cross(a, b, now_ms())
    assert op.gross_profit == 35
    assert op.price_impact == pytest.approx(5)
    assert op.net_profit == pytest.approx(
        35 - op.buy_fee - op.sell_fee - op.estimated_slippage - 0.05
    )


def test_incomparable_sources_and_currency():
    a, b = book(), book("B", bid=102, ask=103)
    b.source = "live"
    assert Detector(config()).cross(a, b, now_ms()) is None
    b.source = "demo"
    b.instrument_id = "OTHER"
    assert Detector(config()).cross(a, b, now_ms()) is None


def test_stale_and_latency_risk():
    a, b = book(), book("B", bid=102, ask=103)
    a.timestamp -= 10000
    assert Detector(config()).scan([a, b]) == []
    a.timestamp = now_ms()
    a.latency_ms = 2000
    op = Detector(config()).cross(a, b, now_ms())
    assert "Latency exceeds limit" in rejection_reasons(op, config())


def test_negative_cycle_and_triangular_fees():
    books = [
        book(symbol="BTC/USDT", bid=99, ask=100),
        book(symbol="ETH/BTC", bid=0.048, ask=0.05),
        book(symbol="ETH/USDT", bid=5.2, ask=5.3),
    ]
    cycles = list(triangular_cycles(books))
    assert len(cycles) == 1
    assert has_negative_cycle(cycles[0])
    op = Detector(
        config(trade_notional=10)
        if False
        else Settings(trade_notional=10, min_confidence_score=0)
    ).triangle(cycles[0], now_ms())
    assert op.gross_profit == pytest.approx(0.4)
    assert op.buy_fee + op.sell_fee == pytest.approx(10.4 * (1 - 0.999**3))
    assert len(op.legs) == 3
    assert all(leg["fee"] > 0 for leg in op.legs)
    assert op.net_profit == pytest.approx(10.4 * 0.999**3 - 10 - 0.003 - 0.05)
    flat = [Edge("a", "b", 1, books[0], "buy"), Edge("b", "a", 1, books[0], "sell")]
    assert not has_negative_cycle(flat)


def test_duplicate_cache():
    cache = MarketCache("")
    a = book()
    assert cache.ingest(a)
    assert not cache.ingest(a)
    older = a.model_copy(update={"sequence": "2", "timestamp": a.timestamp - 100})
    assert not cache.ingest(older)


def test_backtest_chronology():
    a, b = book(), book("B", bid=102, ask=103)
    result = backtest([[a, b]], config())
    assert result["simulated_trades"] == 1
    assert result["by_currency"]["USDT"]["sharpe_like"] is None
    with pytest.raises(ValueError):
        backtest([[a, b], [a, b]], config())


def test_api_execution_and_stream(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        redis_url="",
        snapshot_interval_seconds=3600,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/health").json()["paper_only"] is True
        for _ in range(50):
            opportunities = client.get("/opportunities").json()
            if opportunities:
                break
            time.sleep(0.05)
        assert opportunities
        assert len(client.get("/markets").json()) >= 100
        assert client.get("/orderbooks/Binance/BTC/USDT").status_code == 200
        assert client.get("/opportunities/missing").status_code == 404
        with client.websocket_connect("/ws/market") as socket:
            assert socket.receive_json()["paper_only"] is True
            socket.send_text("ping")
        op = opportunities[0]
        payload = {"opportunity_id": op["id"], "idempotency_key": "integration-test-1"}
        trade = client.post("/paper-trades/execute", json=payload)
        assert trade.status_code == 200, trade.text
        again = client.post("/paper-trades/execute", json=payload)
        assert again.json()["id"] == trade.json()["id"]
        assert len(client.get("/paper-trades").json()) == 1
        portfolio = client.get("/portfolio").json()
        assert portfolio["realized_pnl"] == pytest.approx(trade.json()["net_profit"])
        assert (
            client.post(
                "/paper-trades/execute",
                json={"opportunity_id": "expired", "idempotency_key": "other-key"},
            ).status_code
            == 409
        )
        assert client.post("/paper-trades/execute", json={}).status_code == 422
    # Restore trade history from durable storage after process restart.
    with TestClient(create_app(settings)) as client:
        assert len(client.get("/paper-trades").json()) == 1
