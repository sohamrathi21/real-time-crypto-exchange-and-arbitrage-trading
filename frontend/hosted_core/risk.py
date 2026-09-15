from .models import Opportunity
from .config import Settings


def rejection_reasons(op: Opportunity, settings: Settings) -> list[str]:
    checks = {
        "Net edge below threshold": op.net_profit > 0
        and op.net_edge_percent > settings.min_net_edge_percent,
        "Insufficient liquidity score": op.liquidity_score >= settings.min_liquidity,
        "Slippage exceeds limit": op.slippage_percent <= settings.max_slippage_percent,
        "Stale market data": 0 <= op.price_age_ms <= settings.max_price_age_ms,
        "Latency exceeds limit": op.execution_latency <= settings.max_latency_ms,
        "Trade size exceeds limit": op.capital_required <= settings.max_trade_size,
        "Confidence below threshold": op.confidence_score
        >= settings.min_confidence_score,
    }
    return [reason for reason, passed in checks.items() if not passed]
