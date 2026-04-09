"""
Finance Phase F2-C — Spending Intelligence sub-package.

Ref: Finance Design Rev 3 Section 4.3.

Six metrics across three files:
- `breakdown.py`:      category breakdown (+ hierarchy rollup)
- `trends.py`:         trend detection (1.5× 3-month avg) + anomaly detection
- `patterns.py`:       merchant concentration, spend creep, leakage candidates

Shared constants + category label helpers live in `_helpers.py`. Everything
is re-exported here so callers can import directly from
`server.app.domains.finance.services.spending`.
"""

from server.app.domains.finance.services.spending._helpers import (
    ANOMALY_MULTIPLIER,
    POSTED_STATUSES,
    SPENDING_TYPES,
    TREND_MULTIPLIER,
    _category_label,
    _load_category_map,
)
from server.app.domains.finance.services.spending.breakdown import (
    compute_category_breakdown,
)
from server.app.domains.finance.services.spending.patterns import (
    compute_leakage_candidates,
    compute_merchant_concentration,
    compute_spend_creep,
)
from server.app.domains.finance.services.spending.trends import (
    compute_spending_anomalies,
    compute_spending_trends,
)

__all__ = [
    "ANOMALY_MULTIPLIER",
    "POSTED_STATUSES",
    "SPENDING_TYPES",
    "TREND_MULTIPLIER",
    "_category_label",
    "_load_category_map",
    "compute_category_breakdown",
    "compute_leakage_candidates",
    "compute_merchant_concentration",
    "compute_spend_creep",
    "compute_spending_anomalies",
    "compute_spending_trends",
]
