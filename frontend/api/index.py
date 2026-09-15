"""Read-only, request-driven public market API. No account or trading mutations."""
import asyncio
import time
from fastapi import FastAPI, HTTPException, Response
from hosted_core.config import Settings
from hosted_core.detector import Detector
from hosted_core.analytics import portfolio_stats
from hosted_core.models import now_ms
from hosted_core.providers.live import RestProvider
from hosted_core.news import NewsService
from hosted_core.india import IndiaQuotes

app = FastAPI()
settings = Settings(data_mode='live', auto_paper_trade=False)
news = NewsService()
india = IndiaQuotes()
lock = asyncio.Lock()
cached = None
books_cache = []


async def fetch_venue(name):
    provider = RestProvider(name)
    try:
        books = await asyncio.wait_for(provider.fetch(), timeout=4)
        return books, {'state': 'connected', 'source': 'live', 'transport': 'rest',
                       'latency_ms': max(b.latency_ms for b in books)}
    except Exception:
        return [], {'state': 'unavailable', 'source': 'live',
                    'error': 'Exchange did not return a valid order book within the deadline'}
    finally:
        await provider.close()


async def snapshot():
    global cached, books_cache
    async with lock:
        if cached and now_ms() - cached['timestamp'] < 2000:
            return cached
        names = ['Binance', 'Coinbase', 'Kraken', 'OKX', 'Bybit']
        results = await asyncio.gather(*(fetch_venue(n) for n in names))
        books = [b for group, _ in results for b in group]
        at = now_ms()
        if not any(at - b.timestamp <= settings.max_price_age_ms for b in books):
            raise HTTPException(503, 'Market providers are temporarily unavailable. Retrying automatically.')
        detector = Detector(settings)
        started = time.perf_counter()
        opportunities = detector.scan(books, at)
        detection_ms = (time.perf_counter() - started) * 1000
        prices = [{
            'exchange': b.exchange, 'symbol': b.symbol, 'base': b.base, 'quote': b.quote,
            'bid': b.bids[0].price, 'ask': b.asks[0].price,
            'price': (b.bids[0].price + b.asks[0].price) / 2,
            'spread_percent': (b.asks[0].price / b.bids[0].price - 1) * 100,
            'depth_notional': sum(x.price * x.quantity for x in b.bids + b.asks),
            'source': 'live', 'asset_class': b.asset_class, 'timestamp': b.timestamp,
            'received_at': b.received_at, 'timestamp_origin': b.timestamp_origin,
            'stale': at - b.timestamp > settings.max_price_age_ms,
            'change_24h': None, 'volume_24h': None,
        } for b in books]
        books_cache = books
        cached = dict(timestamp=at, mode='live', transport='polling', prices=prices,
            opportunities=[o.model_dump() for o in opportunities],
            venues=dict(zip(names, [status for _, status in results])),
            portfolio={**portfolio_stats([], settings.starting_capital), 'quote': 'USDT'},
            trades=[], alerts=[], history=[], detection_ms=detection_ms,
            automation=dict(n8n='not hosted', last_success=None, delivery_failures=0,
                queued=0, dropped=0, events=[], config=dict(auto_paper_trade=False,
                high_confidence_alerts=False, min_auto_edge=0.15, min_auto_confidence=85,
                max_auto_capital=10000, max_daily_paper_trades=20, min_liquidity=40)),
            execution=None, replay=dict(enabled=False, playing=False, speed=1, index=0, total=0),
            system=dict(uptime_seconds=0, events_per_second=0, errors=0,
                detected=len(opportunities), expired=0),
            end_to_end_ms=max(b.latency_ms for b in books), rejected=detector.rejected,
            redis='not used', database='read-only hosted mode', paper_only=True,
            settings=settings.model_dump(exclude={'database_url', 'redis_url', 'automation_token', 'n8n_webhook_url'}))
        return cached


@app.get('/api/analytics')
async def analytics(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return await snapshot()


@app.get('/api/health')
async def health():
    return {'status': 'ok', 'mode': 'live', 'transport': 'polling', 'read_only': True}


@app.get('/api/news')
async def headlines():
    return await news.snapshot()


@app.get('/api/india/quotes')
async def indian_quotes():
    return await india.snapshot()


@app.get('/api/billing/status')
async def billing_status():
    return {'configured': False, 'mode': 'unconfigured', 'status': 'inactive', 'plan': None}


@app.get('/api/orderbooks/{exchange}/{symbol:path}')
async def orderbook(exchange: str, symbol: str):
    await snapshot()
    for book in books_cache:
        if book.exchange == exchange and book.symbol == symbol:
            return book.model_dump()
    raise HTTPException(404, 'Order book unavailable')


@app.api_route('/api/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
async def unsupported(path: str):
    raise HTTPException(403, 'Hosted mode provides read-only market data. Use the Arbitrage demo for simulated buying and selling.')
