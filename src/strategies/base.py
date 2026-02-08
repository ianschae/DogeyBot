"""Abstract strategy: stateless, returns buy/sell/hold from candles and in_position."""
from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """Strategy does not track position; caller passes in_position."""

    @abstractmethod
    def get_signal(self, candles: list[dict], in_position: bool) -> str:
        """Return 'buy', 'sell', or 'hold'.
        candles: list of dicts with open, high, low, close, start (ascending by time).
        in_position: True if we currently hold DOGE (from balance > 0).
        """
        pass
