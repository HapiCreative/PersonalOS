"""
Finance Phase F2-C — Derived intelligence router sub-package.

Merges per-entity routers for net worth, cashflow, spending, goal progress,
and investment performance. All endpoints are Derived layer outputs with
DerivedExplanation (Invariant D-01).
"""

from fastapi import APIRouter

from server.app.domains.finance.routers.intelligence.cashflow import (
    router as cashflow_router,
)
from server.app.domains.finance.routers.intelligence.goals import (
    router as goals_router,
)
from server.app.domains.finance.routers.intelligence.investments import (
    router as investments_router,
)
from server.app.domains.finance.routers.intelligence.net_worth import (
    router as net_worth_router,
)
from server.app.domains.finance.routers.intelligence.spending import (
    router as spending_router,
)

router = APIRouter(prefix="/intelligence", tags=["finance-intelligence"])
router.include_router(net_worth_router)
router.include_router(cashflow_router)
router.include_router(spending_router)
router.include_router(goals_router)
router.include_router(investments_router)
