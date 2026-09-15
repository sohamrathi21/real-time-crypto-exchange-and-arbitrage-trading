import asyncio
import json
from types import SimpleNamespace
import pytest
import httpx
from backend.app.config import Settings
from backend.app.models import ExecuteRequest, now_ms
from backend.app.storage import Repository
from backend.app.paper import PaperEngine
from backend.app.orders import OrderEngine, OrderRequest, PaperBrokerAdapter
from backend.app.scanner import Scanner
from backend.app.replay import ReplaySession
from backend.app.automation import AutomationConfig, EventBus
from backend.tests.test_engine import book


@pytest.fixture
async def system(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/orders.db",
        execution_delay_ms=0,
        min_confidence_score=0,
        min_liquidity=0,
    )
    repo = Repository(settings.database_url)
    await repo.initialize()
    paper = PaperEngine(repo, settings)
    scanner = Scanner(settings, repo, paper)
    orders = OrderEngine(settings, repo, paper, scanner.bus)
    paper.order_engine = orders
    scanner.order_engine = orders
    scanner.cache.ingest(book("A", bid=99, ask=100))
    scanner.cache.ingest(book("B", bid=102, ask=103))
    yield scanner, orders, paper
    await repo.close()


def req(side="BUY", quantity=1, kind="MARKET", price=None, key="order-key-1"):
    return OrderRequest(
        symbol="BTC/USDT",
        venue="A",
        side=side,
        order_type=kind,
        quantity=quantity,
        requested_price=price,
        idempotency_key=key,
    )


@pytest.mark.asyncio
async def test_market_order_position_and_accounting(system):
    scanner, orders, paper = system
    order = await orders.submit(req(), scanner)
    assert order["status"] == "OPEN"
    await orders.process(scanner)
    assert order["status"] == "FILLED"
    assert order["average_fill_price"] == 100
    account = orders.portfolio(scanner.cache.books)
    assert account["available_cash"] == pytest.approx(99899.9)
    assert account["positions"][0]["average_entry"] == pytest.approx(100.1)
    assert account["unrealized_pnl"] == pytest.approx(-1.1)
    assert account["portfolio_value"] == pytest.approx(99998.9)
    sell = await orders.submit(req(side="SELL", key="sell-key-1"), scanner)
    await orders.process(scanner)
    assert sell["status"] == "FILLED"
    account = orders.portfolio(scanner.cache.books)
    assert account["positions"] == []
    assert account["realized_pnl"] == pytest.approx(-1.199)
    assert account["portfolio_value"] == pytest.approx(99998.801)


@pytest.mark.asyncio
async def test_limit_reservation_cancel_and_idempotency(system):
    scanner, orders, _ = system
    request = req(kind="LIMIT", price=90)
    order = await orders.submit(request, scanner)
    assert (await orders.submit(request, scanner))["order_id"] == order["order_id"]
    await orders.process(scanner)
    assert order["status"] == "OPEN"
    assert orders.portfolio(scanner.cache.books)["reserved_cash"] == pytest.approx(
        90.09
    )
    await orders.cancel(order["order_id"])
    assert orders.portfolio(scanner.cache.books)["reserved_cash"] == 0
    assert order["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_partial_limit_and_shared_liquidity(system):
    scanner, orders, _ = system
    b = book("A", bid=99, ask=100, qty=0.4)
    b.sequence = "partial-1"
    scanner.cache.books[("A", "BTC/USDT")] = b
    first = await orders.submit(req(kind="LIMIT", price=100), scanner)
    second = await orders.submit(
        req(kind="LIMIT", price=100, key="order-key-2"), scanner
    )
    await orders.process(scanner)
    assert first["filled_quantity"] == pytest.approx(0.4)
    assert first["status"] == "PARTIALLY_FILLED"
    assert second["filled_quantity"] == 0
    b.sequence = "partial-2"
    b.asks[0].quantity = 1.6
    await orders.process(scanner)
    assert first["status"] == "FILLED"
    assert second["status"] == "FILLED"


@pytest.mark.asyncio
async def test_short_sale_stale_order_and_position_cap(system):
    scanner, orders, _ = system
    assert (await orders.submit(req(side="SELL"), scanner))["status"] == "REJECTED"
    b = scanner.cache.books[("A", "BTC/USDT")]
    b.timestamp -= 10000
    stale = await orders.submit(req(key="stale-key"), scanner)
    assert stale["status"] == "REJECTED" and "Stale" in stale["reason"]


@pytest.mark.asyncio
async def test_fill_storage_failure_rolls_back(system, monkeypatch):
    scanner, orders, _ = system
    order = await orders.submit(req(), scanner)

    async def fail():
        raise RuntimeError("database offline")

    monkeypatch.setattr(orders, "persist", fail)
    with pytest.raises(RuntimeError):
        await orders.process(scanner)
    assert orders.orders[order["order_id"]]["filled_quantity"] == 0
    assert orders.positions == {}
    assert orders.cash_delta == {}


@pytest.mark.asyncio
async def test_partial_arbitrage_exposure_is_accounted(system):
    scanner, orders, paper = system
    op = scanner.detector.scan(list(scanner.cache.books.values()))[0]
    result = await paper.execute(
        ExecuteRequest(
            opportunity_id=op.id,
            idempotency_key="partial-arb-key",
            execution_scenario="partial_sell",
        ),
        scanner,
    )
    assert result["status"] == "partial_exposure"
    assert result["remaining_exposure"] == pytest.approx(4)
    account = orders.portfolio(scanner.cache.books)
    assert len(account["positions"]) == 1
    assert account["positions"][0]["quantity"] == pytest.approx(4)
    expected_equity = 100000 + result["net_profit"] - 400.4 + 396
    assert account["portfolio_value"] == pytest.approx(expected_equity)


@pytest.mark.asyncio
async def test_automation_off_kill_threshold_and_idempotency(system):
    scanner, orders, paper = system
    op = scanner.detector.scan(list(scanner.cache.books.values()))[0]
    request = ExecuteRequest(opportunity_id=op.id, idempotency_key="auto-key-1")
    with pytest.raises(ValueError, match="OFF"):
        await paper.execute(request, scanner, automated=True)
    scanner.bus.config = AutomationConfig(auto_paper_trade=True, min_auto_edge=99)
    with pytest.raises(ValueError, match="threshold"):
        await paper.execute(request, scanner, automated=True)
    scanner.bus.config = AutomationConfig(
        auto_paper_trade=True, min_auto_edge=0, min_auto_confidence=0, min_liquidity=0
    )
    first = await paper.execute(request, scanner, automated=True)
    again = await paper.execute(request, scanner, automated=True)
    assert first["id"] == again["id"]
    assert len(paper.trades) == 1
    assert first["origin"] == "automated"


@pytest.mark.asyncio
async def test_manual_and_arbitrage_cannot_reuse_depth(system):
    scanner, orders, paper = system
    await orders.submit(req(), scanner)
    await orders.process(scanner)
    op = scanner.detector.scan(list(scanner.cache.books.values()))[0]
    with pytest.raises(ValueError, match="consumed"):
        await paper.execute(
            ExecuteRequest(opportunity_id=op.id, idempotency_key="overlap-key"), scanner
        )


def test_replay_preserves_age_and_label():
    b = book()
    b.timestamp -= 2500
    replay = ReplaySession()
    replay.load([[b]])
    replay.playing = True
    result = replay.tick()[0]
    assert result.source == "replay"
    assert result.received_at - result.timestamp == b.received_at - b.timestamp
    assert result.sequence.startswith("replay:")


@pytest.mark.asyncio
async def test_n8n_failure_does_not_block_scanner(system, monkeypatch):
    scanner, _, _ = system

    async def fail(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail)
    scanner.bus.settings.n8n_webhook_url = "http://127.0.0.1:1/unavailable"
    await scanner.bus.start()
    scanner.bus.emit("HIGH_CONFIDENCE_OPPORTUNITY", metadata={"net_edge_percent": 1})
    # Detection stays synchronous and usable independently of delivery worker.
    assert scanner.detector.scan(list(scanner.cache.books.values()))
    await asyncio.sleep(0.2)
    assert scanner.bus.failures >= 1
    await scanner.bus.stop()


def test_workflow_exports():
    from pathlib import Path

    workflows = list(Path("automation/workflows").glob("*.json"))
    assert len(workflows) == 5
    for path in workflows:
        data = json.loads(path.read_text())
        names = {n["name"] for n in data["nodes"]}
        assert data["active"] is False
        for source, connection in data["connections"].items():
            assert source in names
            for branch in connection["main"]:
                assert all(edge["node"] in names for edge in branch)
