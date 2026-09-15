import asyncio
import contextlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from .config import Settings
from .models import ExecuteRequest, BacktestRequest
from .storage import Repository
from .paper import PaperEngine
from .scanner import Scanner
from .backtest import backtest
from .orders import OrderEngine, OrderRequest
from .automation import AutomationConfig
from .replay import ReplayControl
from .billing import Billing
from .news import NewsService
from .india import IndiaQuotes
from .models import now_ms
from .storage import record


def create_app(settings=None):
    settings = settings or Settings()
    if settings.data_mode not in ("demo", "live"):
        raise ValueError("DATA_MODE must be demo or live")
    news = NewsService()
    india = IndiaQuotes()
    repository = Repository(settings.database_url)
    paper = PaperEngine(repository, settings)
    scanner = Scanner(settings, repository, paper)
    orders = OrderEngine(settings, repository, paper, scanner.bus)
    scanner.order_engine = orders
    paper.order_engine = orders

    @asynccontextmanager
    async def lifespan(app):
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        await repository.initialize()
        await paper.load()
        await orders.load()
        await scanner.start()
        order_task = asyncio.create_task(orders.run(scanner))
        yield
        order_task.cancel()
        await asyncio.gather(order_task, return_exceptions=True)
        await scanner.stop()
        await repository.close()

    app = FastAPI(
        title="ARBITRAGE X · Paper Trading API", version="1.0.0", lifespan=lifespan
    )
    app.state.scanner, app.state.paper = scanner, paper
    app.include_router(Billing(repository, scanner.bus).router())
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://localhost:8080"
        ).split(","),
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    async def health():
        return {
            "status": "ok" if scanner.running else "starting",
            "paper_only": True,
            "mode": settings.data_mode,
            "database": scanner.persistence_status,
            "redis": scanner.cache.status,
        }

    @app.get("/india/quotes")
    async def indian_quotes():
        return await india.snapshot()

    @app.get("/news")
    async def market_news():
        return await news.snapshot()

    @app.get("/markets")
    async def markets():
        return [
            {
                "symbol": b.symbol,
                "exchange": b.exchange,
                "source": b.source,
                "asset_class": b.asset_class,
            }
            for b in scanner.cache.books.values()
        ]

    @app.get("/prices")
    async def prices():
        return scanner.prices()

    @app.get("/orderbooks/{exchange}/{symbol:path}")
    async def orderbooks(exchange: str, symbol: str):
        book = scanner.cache.books.get((exchange, symbol))
        if not book:
            raise HTTPException(404, "Order book not found")
        return book

    @app.get("/opportunities")
    async def opportunities():
        return scanner.opportunities

    @app.get("/opportunities/{identifier:path}")
    async def opportunity(identifier: str):
        op = next((o for o in scanner.opportunities if o.id == identifier), None)
        if not op:
            raise HTTPException(404, "Opportunity expired or unavailable")
        return op

    @app.get("/portfolio")
    async def portfolio(quote: str = "USDT"):
        return paper.portfolio(quote)

    @app.get("/paper-trades")
    async def paper_trades():
        return list(reversed(paper.trades))

    @app.post("/paper-trades/execute")
    async def execute(request: ExecuteRequest):
        try:
            trade = await paper.execute(request, scanner)
            scanner.lifecycle.executed(request.opportunity_id)
            scanner.bus.emit(
                "PAPER_TRADE_EXECUTED",
                trade["symbol"],
                trade["source"],
                trade["buy_venue"],
                metadata=trade,
            )
            return trade
        except ValueError as exc:
            scanner.bus.emit(
                "PAPER_TRADE_REJECTED",
                severity="warning",
                metadata={"reason": str(exc), "opportunity_id": request.opportunity_id},
            )
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            logging.exception("Paper execution persistence failure")
            raise HTTPException(
                503, "Could not persist paper trade; no trade acknowledged"
            ) from exc

    @app.get("/orders")
    async def get_orders():
        return orders.snapshot(scanner.cache.books)

    @app.post("/orders")
    async def place_order(request: OrderRequest):
        try:
            return await orders.submit(request, scanner)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/orders/{identifier}/cancel")
    async def cancel_order(identifier: str):
        try:
            return await orders.cancel(identifier)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/positions")
    async def positions(quote: str = "USDT"):
        return orders.portfolio(scanner.cache.books, quote)

    @app.get("/automation")
    async def automation():
        return scanner.bus.snapshot()

    @app.put("/automation/config")
    async def automation_config(config: AutomationConfig):
        return await scanner.bus.configure(config)

    @app.post("/automation/kill")
    async def kill():
        config = scanner.bus.config.model_copy(update={"auto_paper_trade": False})
        # Disarm memory before persistence so storage outages cannot keep automation armed.
        scanner.bus.config = config
        return await scanner.bus.configure(config)

    def authorize(token):
        if not settings.automation_token or not secrets.compare_digest(
            token or "", settings.automation_token
        ):
            raise HTTPException(401, "Automation token missing or invalid")

    @app.post("/automation/execute")
    async def auto_execute(
        request: ExecuteRequest, x_automation_token: str | None = Header(None)
    ):
        authorize(x_automation_token)
        cfg = scanner.bus.config
        if not cfg.auto_paper_trade:
            raise HTTPException(409, "Auto paper trading is OFF")
        today = datetime.now(timezone.utc).date()
        daily = sum(
            datetime.fromtimestamp(t["timestamp"] / 1000, timezone.utc).date() == today
            for t in paper.trades
        )
        if daily >= cfg.max_daily_paper_trades:
            raise HTTPException(409, "Daily paper trade limit reached")
        op = next(
            (o for o in scanner.opportunities if o.id == request.opportunity_id), None
        )
        if (
            not op
            or op.net_edge_percent < cfg.min_auto_edge
            or op.confidence_score < cfg.min_auto_confidence
            or op.capital_required > cfg.max_auto_capital
            or op.liquidity_score < cfg.min_liquidity
        ):
            raise HTTPException(409, "Opportunity fails automation thresholds")
        try:
            trade = await paper.execute(request, scanner, automated=True)
            scanner.bus.emit(
                "PAPER_TRADE_EXECUTED",
                trade["symbol"],
                trade["source"],
                trade["buy_venue"],
                metadata=trade,
            )
            return trade
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/automation/notify")
    async def notify_event(
        payload: dict, x_automation_token: str | None = Header(None)
    ):
        authorize(x_automation_token)
        event_id = str(payload.get("event_id", ""))[:128]
        if not event_id:
            raise HTTPException(422, "event_id is required")
        existing = await repository.list("workflow_notification", 10000)
        if any(e.get("event_id") == event_id for e in existing):
            return {"status": "duplicate"}
        await repository.put_many([record("workflow_notification", event_id, payload)])
        scanner.bus.emit("AUTOMATION_ALERT", metadata=payload)
        return {"status": "recorded"}

    @app.post("/reports")
    async def generate_report():
        report = {
            "id": str(uuid.uuid4()),
            "timestamp": now_ms(),
            "markets_monitored": len(scanner.cache.books),
            "opportunities_detected": scanner.lifecycle.detected,
            "qualified_opportunities": len(scanner.opportunities),
            "rejected_current_scan": scanner.detector.rejected,
            "paper_trades": len(paper.trades),
            "pnl_by_currency": {},
            "best_opportunity": (
                scanner.opportunities[0].model_dump() if scanner.opportunities else None
            ),
            "average_confidence": (
                sum(o.confidence_score for o in scanner.opportunities)
                / len(scanner.opportunities)
                if scanner.opportunities
                else None
            ),
            "average_detection_latency_ms": (
                sum(h["latency_ms"] for h in scanner.history) / len(scanner.history)
                if scanner.history
                else None
            ),
        }
        for quote in {t["quote"] for t in paper.trades}:
            trades = [t for t in paper.trades if t["quote"] == quote]
            report["pnl_by_currency"][quote] = {
                k: sum(t[k] for t in trades)
                for k in [
                    "gross_profit",
                    "buy_fee",
                    "sell_fee",
                    "estimated_slippage",
                    "net_profit",
                ]
            }
        await repository.put_many([record("session_report", report["id"], report)])
        return report

    @app.get("/reports")
    async def reports():
        return await repository.list("session_report", 100)

    @app.get("/system")
    async def system():
        state = scanner.snapshot()
        return {
            key: state[key]
            for key in [
                "system",
                "venues",
                "database",
                "redis",
                "automation",
                "detection_ms",
                "end_to_end_ms",
            ]
        }

    @app.post("/replay/load")
    async def load_replay(request: BacktestRequest):
        async with scanner.lock:
            try:
                scanner.replay.load(request.frames)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            scanner.cache.books.clear()
            scanner.opportunities = []
            scanner.price_history.clear()
        return scanner.replay.snapshot()

    @app.post("/replay/control")
    async def replay_control(control: ReplayControl):
        if control.action not in ["play", "pause", "stop"]:
            raise HTTPException(422, "Action must be play, pause or stop")
        if control.speed not in [1, 2, 5, 10]:
            raise HTTPException(422, "Speed must be 1, 2, 5 or 10")
        async with scanner.lock:
            if control.action == "stop":
                scanner.replay.enabled = False
                scanner.replay.playing = False
                scanner.cache.books.clear()
                scanner.opportunities = []
                scanner.price_history.clear()
            else:
                if not scanner.replay.frames:
                    raise HTTPException(409, "Load recorded frames first")
                scanner.replay.speed = control.speed
                scanner.replay.playing = control.action == "play"
        return scanner.replay.snapshot()

    @app.get("/history/{exchange}/{symbol:path}")
    async def price_history(exchange: str, symbol: str):
        return list(scanner.price_history.get(f"{exchange}:{symbol}", []))

    @app.get("/analytics")
    async def analytics():
        return scanner.snapshot()

    @app.post("/backtest")
    async def run_backtest(request: BacktestRequest):
        try:
            return await asyncio.to_thread(backtest, request.frames, settings)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.websocket("/ws/orderbook/{exchange}/{symbol:path}")
    async def orderbook_stream(socket: WebSocket, exchange: str, symbol: str):
        await socket.accept()
        try:
            while True:
                book = scanner.cache.books.get((exchange, symbol))
                await socket.send_json(
                    book.model_dump() if book else {"error": "Book unavailable"}
                )
                await asyncio.sleep(0.5)
        except (WebSocketDisconnect, RuntimeError):
            pass

    async def stream(socket: WebSocket):
        await socket.accept()
        queue = asyncio.Queue(maxsize=1)
        scanner.subscribers.add(queue)

        async def receive():
            while True:
                message = await socket.receive_text()
                if message != "ping":
                    # No control or trading instructions accepted on streaming sockets.
                    continue

        receiver = asyncio.create_task(receive())
        try:
            await socket.send_json(scanner.snapshot())
            while not receiver.done():
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=10)
                except asyncio.TimeoutError:
                    payload = {"type": "heartbeat"}
                await socket.send_json(payload)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            scanner.subscribers.discard(queue)
            receiver.cancel()
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                await receiver

    app.websocket("/ws/market")(stream)
    app.websocket("/ws/opportunities")(stream)
    return app


app = create_app()
