from dataclasses import dataclass
from .models import Level


class InsufficientLiquidity(ValueError):
    pass


@dataclass
class Fill:
    quantity: float
    notional: float
    vwap: float
    impact: float


def sweep(levels: list[Level], quantity: float) -> Fill:
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    remaining, total = quantity, 0.0
    for level in levels:
        take = min(remaining, level.quantity)
        total += take * level.price
        remaining -= take
        if remaining < quantity * 1e-10:
            break
    if remaining > quantity * 1e-8:
        raise InsufficientLiquidity("Requested size exceeds displayed depth")
    vwap = total / quantity
    return Fill(quantity, total, vwap, abs(vwap - levels[0].price) * quantity)


def buy_with_budget(levels: list[Level], budget: float) -> Fill:
    if budget <= 0:
        raise ValueError("Budget must be positive")
    remaining, quantity = budget, 0.0
    for level in levels:
        spend = min(remaining, level.price * level.quantity)
        quantity += spend / level.price
        remaining -= spend
        if remaining < budget * 1e-10:
            break
    if remaining > budget * 1e-8:
        raise InsufficientLiquidity("Budget exceeds displayed depth")
    return Fill(
        quantity, budget, budget / quantity, budget - quantity * levels[0].price
    )
