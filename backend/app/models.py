import math
import time
from typing import Literal
from pydantic import BaseModel, Field, model_validator


def now_ms() -> int:
    return int(time.time() * 1000)


class Level(BaseModel):
    price: float = Field(gt=0, allow_inf_nan=False)
    quantity: float = Field(gt=0, allow_inf_nan=False)


class OrderBook(BaseModel):
    exchange: str
    symbol: str
    base: str
    quote: str
    bids: list[Level] = Field(min_length=1)
    asks: list[Level] = Field(min_length=1)
    timestamp: int
    received_at: int = Field(default_factory=now_ms)
    exchange_timestamp: int | None = None
    timestamp_origin: str = "provider_or_request_start"
    sequence: str
    latency_ms: float = Field(ge=0, allow_inf_nan=False)
    fee_rate: float = Field(ge=0, lt=1, allow_inf_nan=False)
    source: Literal["demo", "live", "replay"] = "demo"
    asset_class: Literal["crypto", "equity"] = "crypto"
    instrument_id: str = ""
    settlement: str = "spot-prefunded"
    market_open: bool = True

    @model_validator(mode="after")
    def validate_book(self):
        self.bids.sort(key=lambda x: x.price, reverse=True)
        self.asks.sort(key=lambda x: x.price)
        if self.bids[0].price >= self.asks[0].price:
            raise ValueError("Crossed or locked order book")
        if self.symbol != f"{self.base}/{self.quote}":
            raise ValueError("Symbol must match base/quote")
        if self.timestamp > self.received_at + 1000:
            raise ValueError("Future-dated order book")
        return self


class Opportunity(BaseModel):
    id: str
    symbol: str
    type: Literal["cross_exchange", "triangular", "cross_venue"]
    buy_venue: str
    sell_venue: str
    source: str
    quote: str
    buy_price: float
    sell_price: float
    trade_quantity: float
    gross_profit: float
    buy_fee: float
    sell_fee: float
    estimated_slippage: float
    price_impact: float
    slippage_percent: float
    network_cost: float = 0
    other_costs: float
    net_profit: float
    gross_spread_percent: float
    net_edge_percent: float
    capital_required: float
    roi: float
    execution_latency: float
    liquidity_score: float
    available_liquidity: float
    confidence_score: float
    confidence_factors: dict[str, float]
    timestamp: int
    first_seen: int
    price_age_ms: int
    path: list[str] = []
    legs: list[dict] = []
    assumptions: list[str] = []


class ExecuteRequest(BaseModel):
    opportunity_id: str
    execution_scenario: Literal["normal", "partial_sell", "price_moved"] = "normal"
    idempotency_key: str = Field(min_length=8, max_length=128)


class BacktestRequest(BaseModel):
    frames: list[list[OrderBook]] = Field(min_length=1, max_length=2000)
