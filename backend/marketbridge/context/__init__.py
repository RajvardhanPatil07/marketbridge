"""Context-plane adapters.

Context can explain or tighten human review, but it never creates Market Truth.
"""

from .intelligence import get_market_intelligence
from .sec import get_company_snapshot

__all__ = ["get_company_snapshot", "get_market_intelligence"]
