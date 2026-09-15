import math
import random
from ..models import OrderBook, Level, now_ms
from .base import MarketDataProvider

ASSETS = dict(
    BTC=67240,
    ETH=3520,
    SOL=148,
    AVAX=32,
    LINK=14.2,
    XRP=0.58,
    ADA=0.38,
    DOT=6.1,
    DOGE=0.12,
    LTC=72,
    BCH=380,
    UNI=7.4,
    ATOM=6.4,
    NEAR=4.8,
    APT=7.8,
    ARB=0.72,
    OP=1.8,
    SUI=1.1,
    INJ=24,
    FIL=4.6,
    AAVE=112,
    TON=6.8,
)
VENUES = ["Binance", "Coinbase", "Kraken", "OKX", "Bybit"]
FEES = {
    "Binance": 0.001,
    "Coinbase": 0.002,
    "Kraken": 0.0016,
    "OKX": 0.001,
    "Bybit": 0.001,
}


class MockProvider(MarketDataProvider):
    source = "demo"

    def __init__(self, seed=42):
        self.name = "Simulation"
        self.rng = random.Random(seed)
        self.tick = 0
        self.prices = ASSETS.copy()

    def book(self, venue, base, quote, mid, asset_class="crypto"):
        spread = 0.00018 if asset_class == "crypto" else 0.0003
        liquidity = self.rng.uniform(5000, 18000)
        if quote == "BTC":
            liquidity /= self.prices["BTC"]
        stamp = now_ms()
        return OrderBook(
            exchange=venue,
            symbol=f"{base}/{quote}",
            base=base,
            quote=quote,
            bids=[
                Level(
                    price=mid * (1 - spread - i * 0.00012),
                    quantity=liquidity / mid * (1 + i * 0.4),
                )
                for i in range(12)
            ],
            asks=[
                Level(
                    price=mid * (1 + spread + i * 0.00012),
                    quantity=liquidity / mid * (1 + i * 0.4),
                )
                for i in range(12)
            ],
            timestamp=stamp - self.rng.randint(15, 65),
            received_at=stamp,
            sequence=str(self.tick),
            latency_ms=self.rng.uniform(18, 90),
            fee_rate=FEES.get(venue, 0.0005),
            source="demo",
            asset_class=asset_class,
            instrument_id=f"{base}:{quote}:{asset_class}",
        )

    async def fetch(self):
        self.tick += 1
        books = []
        for index, (base, price) in enumerate(self.prices.items()):
            price *= math.exp(self.rng.gauss(0, 0.00015))
            self.prices[base] = price
            # Smooth, temporary dislocations; gaps close without user interaction.
            pulse = max(0, math.sin(self.tick * 0.19 + index * 1.8)) ** 3 * 0.0068
            for v, venue in enumerate(VENUES):
                offset = (
                    pulse
                    if v == index % 5
                    else -pulse * 0.22 if v == (index + 1) % 5 else 0
                )
                mid = price * (1 + offset + self.rng.gauss(0, 0.00006))
                books.append(self.book(venue, base, "USDT", mid))
        for v, venue in enumerate(VENUES):
            ethbtc = self.prices["ETH"] / self.prices["BTC"]
            distortion = max(0, math.sin(self.tick * 0.14 + v)) ** 4 * 0.009
            books.append(self.book(venue, "ETH", "BTC", ethbtc * (1 - distortion)))
        for base, price in [("AAPL", 218), ("MSFT", 438), ("NVDA", 128)]:
            for v, venue in enumerate(["NASDAQ-SIM", "NYSE-SIM"]):
                mid = price * (1 + 0.0004 * math.sin(self.tick * 0.12) + v * 0.0002)
                books.append(self.book(venue, base, "USD", mid, "equity"))
        return books
