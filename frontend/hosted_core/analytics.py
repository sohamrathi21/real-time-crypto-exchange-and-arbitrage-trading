from .config import Settings


def confidence(
    *,
    edge: float,
    liquidity: float,
    depth: int,
    age: int,
    latency: float,
    duration: float,
    slippage: float,
    volatility: float,
    reliability: float,
    settings: Settings
):
    clamp = lambda x: max(0, min(100, x))
    factors = {
        "spread": clamp(55 + edge * 100),
        "liquidity": clamp(liquidity),
        "depth": clamp(depth * 10),
        "freshness": clamp(100 * (1 - age / settings.max_price_age_ms)),
        "latency": clamp(100 * (1 - latency / settings.max_latency_ms)),
        "persistence": clamp(50 + duration * 8),
        "slippage": clamp(100 * (1 - slippage / settings.max_slippage_percent)),
        "volatility": clamp(100 - volatility * 10000),
        "reliability": clamp(reliability * 100),
    }
    weights = settings.confidence_weights
    if (
        set(weights) != set(factors)
        or any(v < 0 for v in weights.values())
        or sum(weights.values()) <= 0
    ):
        raise ValueError(
            "Confidence weights must cover all factors and have positive total"
        )
    return (
        round(sum(factors[k] * weights[k] for k in factors) / sum(weights.values()), 1),
        factors,
    )


def portfolio_stats(trades: list[dict], starting: float) -> dict:
    pnl = sum(t["net_profit"] for t in trades)
    equity, peak, drawdown = starting, starting, 0.0
    curve = [{"timestamp": 0, "equity": starting, "pnl": 0}]
    for trade in sorted(trades, key=lambda t: t["timestamp"]):
        equity += trade["net_profit"]
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak * 100)
        curve.append(
            {
                "timestamp": trade["timestamp"],
                "equity": equity,
                "pnl": equity - starting,
            }
        )
    return {
        "starting_capital": starting,
        "available_capital": starting + pnl,
        "realized_pnl": pnl,
        "unrealized_pnl": 0,
        "number_of_trades": len(trades),
        "win_rate": (
            sum(t["net_profit"] > 0 for t in trades) / len(trades) * 100
            if trades
            else 0
        ),
        "average_return": sum(t["roi"] for t in trades) / len(trades) if trades else 0,
        "maximum_drawdown": drawdown,
        "curve": curve,
        "accounting": "One pooled quote-currency ledger per currency; prefunded inventory assumed. No live transfers.",
    }
