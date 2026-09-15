import statistics
from .detector import Detector
from .analytics import portfolio_stats


def backtest(frames, settings):
    detector = Detector(settings)
    trades, count, durations, last = [], 0, {}, -1
    for frame in frames:
        if not frame:
            continue
        at = max(b.received_at for b in frame)
        if at <= last:
            raise ValueError("Frames must be strictly chronological")
        last = at
        opportunities = detector.scan(frame, at)
        count += len(opportunities)
        for op in opportunities:
            durations.setdefault(op.id, [at, at])[1] = at
        # One highest-ranked fill per frame, avoiding overlapping displayed liquidity.
        if opportunities:
            op = opportunities[0]
            equity = settings.starting_capital + sum(
                t["net_profit"] for t in trades if t["quote"] == op.quote
            )
            if op.capital_required <= equity:
                trades.append(op.model_dump())
    quotes = sorted({t["quote"] for t in trades})
    results = {}
    for quote in quotes:
        subset = [t for t in trades if t["quote"] == quote]
        stats = portfolio_stats(subset, settings.starting_capital)
        returns = [t["roi"] / 100 for t in subset]
        deviation = statistics.stdev(returns) if len(returns) > 1 else 0
        results[quote] = {
            **stats,
            "gross_pnl": sum(t["gross_profit"] for t in subset),
            "fees": sum(t["buy_fee"] + t["sell_fee"] for t in subset),
            "slippage": sum(t["estimated_slippage"] for t in subset),
            "sharpe_like": (
                statistics.mean(returns) / deviation if deviation > 0 else None
            ),
        }
    return {
        "opportunities": count,
        "simulated_trades": len(trades),
        "by_currency": results,
        "average_opportunity_duration_seconds": (
            statistics.mean((b - a) / 1000 for a, b in durations.values())
            if durations
            else 0
        ),
        "assumptions": [
            "Full depth snapshots required; no interpolation of last-trade prices.",
            "At most one fill per frame; prefunded inventory and instantaneous paired fills.",
            "Sharpe-like metric is per-trade, unannualized; null for insufficient variance.",
            "Duration is first-to-last observed span and may include unobserved gaps.",
            "Currencies are reported separately. Not a prediction of live returns.",
        ],
    }
