"""MarketBridge v1 application entrypoint.

The mature API remains in :mod:`marketbridge.api`; this module layers the free-first
provider/intelligence and judge-facing War Room routes without duplicating the core.
"""

from .api import app, pipeline, risk_gateway
from .v1free import install_v1_free

install_v1_free(app, pipeline, risk_gateway)

__all__ = ["app"]
