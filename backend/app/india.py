import asyncio
import math
import os
import time
import httpx

# A curated starting list, not a claim to cover every listed security.
INDIAN_STOCKS = [
    ('RELIANCE', 'Reliance Industries', 'Energy'), ('TCS', 'Tata Consultancy Services', 'IT'),
    ('HDFCBANK', 'HDFC Bank', 'Banking'), ('ICICIBANK', 'ICICI Bank', 'Banking'),
    ('INFY', 'Infosys', 'IT'), ('SBIN', 'State Bank of India', 'Banking'),
    ('BHARTIARTL', 'Bharti Airtel', 'Telecom'), ('ITC', 'ITC', 'Consumer'),
    ('LT', 'Larsen & Toubro', 'Industrials'), ('HINDUNILVR', 'Hindustan Unilever', 'Consumer'),
    ('AXISBANK', 'Axis Bank', 'Banking'), ('KOTAKBANK', 'Kotak Mahindra Bank', 'Banking'),
    ('BAJFINANCE', 'Bajaj Finance', 'Finance'), ('MARUTI', 'Maruti Suzuki', 'Auto'),
    ('SUNPHARMA', 'Sun Pharmaceutical', 'Healthcare'), ('TITAN', 'Titan Company', 'Consumer'),
    ('NTPC', 'NTPC', 'Utilities'), ('POWERGRID', 'Power Grid Corporation', 'Utilities'),
    ('HCLTECH', 'HCL Technologies', 'IT'), ('WIPRO', 'Wipro', 'IT'),
]

def number(value):
    return float(value) if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None

class IndiaQuotes:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.checked = 0
        self.result = None

    async def snapshot(self):
        async with self.lock:
            if self.result and time.monotonic() - self.checked < 10:
                return self.result
            key, token = os.getenv('KITE_API_KEY', ''), os.getenv('KITE_ACCESS_TOKEN', '')
            configured = bool(key and token)
            status, message, quotes = 'not_configured', 'Connect a Kite market-data subscription to load actual Indian stock prices.', {}
            if configured:
                try:
                    async with httpx.AsyncClient(timeout=12) as client:
                        response = await client.get('https://api.kite.trade/quote',
                            params=[('i', 'NSE:' + s[0]) for s in INDIAN_STOCKS],
                            headers={'X-Kite-Version': '3', 'Authorization': f'token {key}:{token}'})
                    response.raise_for_status()
                    payload = response.json()
                    if payload.get('status') != 'success' or not isinstance(payload.get('data'), dict):
                        raise ValueError('Invalid quote response')
                    quotes = payload['data']
                    status, message = 'connected', 'Kite quote snapshots refresh every 10 seconds. Check exchange timestamps; markets may be closed.'
                except httpx.HTTPStatusError as exc:
                    status = 'unavailable'
                    message = 'Kite access expired or not entitled to market data.' if exc.response.status_code in (401,403) else 'Kite quote service is temporarily unavailable.'
                except (httpx.HTTPError, ValueError):
                    status, message = 'unavailable', 'Kite quote service is temporarily unavailable.'
            rows = []
            for symbol, name, sector in INDIAN_STOCKS:
                q = quotes.get('NSE:' + symbol, {})
                price = number(q.get('last_price'))
                close = number(q.get('ohlc', {}).get('close'))
                rows.append(dict(symbol=symbol, name=name, sector=sector, exchange='NSE', currency='INR',
                    price=price, change_percent=(price-close)/close*100 if price is not None and close else None,
                    timestamp=q.get('timestamp'), source='Kite' if price is not None else 'unavailable'))
            self.result = dict(configured=configured,status=status,message=message,stocks=rows,
                               fetched_at=int(time.time()*1000),refresh_seconds=10)
            self.checked = time.monotonic()
            return self.result
