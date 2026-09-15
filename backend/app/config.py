from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    data_mode: str = "demo"
    n8n_webhook_url: str = ""
    automation_token: str = ""
    auto_paper_trade: bool = False
    min_auto_edge: float = Field(0.15, ge=0)
    min_auto_confidence: float = Field(85, ge=0, le=100)
    max_auto_capital: float = Field(10000, gt=0)
    max_daily_paper_trades: int = Field(20, ge=1)
    max_position_notional: float = Field(25000, gt=0)
    max_drawdown_percent: float = Field(15, gt=0, le=100)
    execution_delay_ms: int = Field(80, ge=0, le=1000)
    database_url: str = "sqlite+aiosqlite:///./arbitrage.db"
    redis_url: str = ""
    min_net_edge_percent: float = Field(0.03, ge=0)
    min_liquidity: float = Field(40, ge=0, le=100)
    max_slippage_percent: float = Field(0.25, gt=0)
    max_price_age_ms: int = Field(5000, gt=0)
    max_latency_ms: int = Field(1500, gt=0)
    max_trade_size: float = Field(10000, gt=0)
    trade_notional: float = Field(1000, gt=0)
    min_confidence_score: float = Field(60, ge=0, le=100)
    starting_capital: float = Field(100000, gt=0)
    snapshot_interval_seconds: int = Field(30, ge=1)
    residual_slippage_bps: float = Field(1, ge=0)
    other_cost: float = Field(0.05, ge=0)
    confidence_weights: dict[str, float] = {
        "spread": 0.16,
        "liquidity": 0.15,
        "depth": 0.1,
        "freshness": 0.15,
        "latency": 0.1,
        "persistence": 0.1,
        "slippage": 0.1,
        "volatility": 0.06,
        "reliability": 0.08,
    }


settings = Settings()
