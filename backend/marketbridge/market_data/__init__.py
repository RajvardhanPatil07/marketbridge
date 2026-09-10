"""Display-only historical market data.

Nothing in this package contributes oracle evidence.  The qualification boundary
continues to live in :mod:`marketbridge.shadow`.
"""

from .alpaca_history import AlpacaHistoricalProvider
from .service import HistoricalMarketDataService

__all__ = ["AlpacaHistoricalProvider", "HistoricalMarketDataService"]
