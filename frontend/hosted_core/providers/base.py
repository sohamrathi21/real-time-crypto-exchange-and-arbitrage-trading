from abc import ABC, abstractmethod
from ..models import OrderBook


class MarketDataProvider(ABC):
    name: str
    source: str

    @abstractmethod
    async def fetch(self) -> list[OrderBook]:
        """Return validated full-depth snapshots. Never place orders."""

    async def close(self):
        pass
