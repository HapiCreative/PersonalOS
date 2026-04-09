"""
Finance Phase F2-C — Investment Performance (Derived layer).

Ref: Finance Design Rev 3 Section 4.5.

Re-exports the public API so callers can keep importing from
`server.app.domains.finance.services.investment_performance`.
Internal helpers are intentionally exposed for rollup sub-modules.
"""

from server.app.domains.finance.services.investment_performance._helpers import (
    _compute_account_invested,
    _compute_realized_gain,
    _get_latest_holdings,
    _get_latest_price,
    _list_investment_accounts,
    _sum_dividends,
)
from server.app.domains.finance.services.investment_performance.aggregate import (
    compute_aggregate_performance,
)
from server.app.domains.finance.services.investment_performance.account import (
    compute_account_performance,
)

__all__ = [
    "_compute_account_invested",
    "_compute_realized_gain",
    "_get_latest_holdings",
    "_get_latest_price",
    "_list_investment_accounts",
    "_sum_dividends",
    "compute_account_performance",
    "compute_aggregate_performance",
]
