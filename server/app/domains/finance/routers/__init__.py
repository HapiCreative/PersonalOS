"""Finance domain routers — merges all entity routers into one."""

from fastapi import APIRouter

from server.app.domains.finance.routers.accounts import router as accounts_router
from server.app.domains.finance.routers.allocations import router as allocations_router
from server.app.domains.finance.routers.balance import router as balance_router
from server.app.domains.finance.routers.categories import router as categories_router
from server.app.domains.finance.routers.csv_import import router as csv_import_router
from server.app.domains.finance.routers.exchange_rates import router as exchange_rates_router
from server.app.domains.finance.routers.intelligence import (
    router as intelligence_router,
)
from server.app.domains.finance.routers.investments import router as investments_router
from server.app.domains.finance.routers.market_prices import router as market_prices_router
from server.app.domains.finance.routers.obligation_breakdowns import (
    router as obligation_breakdowns_router,
)
from server.app.domains.finance.routers.obligations import router as obligations_router
from server.app.domains.finance.routers.rollups import router as rollups_router
from server.app.domains.finance.routers.transactions import router as transactions_router
from server.app.domains.finance.routers.transfers import router as transfers_router

router = APIRouter(prefix="/api/finance", tags=["finance"])

router.include_router(accounts_router)
router.include_router(categories_router)
router.include_router(allocations_router)
router.include_router(balance_router)
router.include_router(transactions_router)
router.include_router(transfers_router)
router.include_router(csv_import_router)

# F2-B: Investment + Obligation routers
router.include_router(investments_router)
router.include_router(exchange_rates_router)
router.include_router(market_prices_router)
router.include_router(obligations_router)
router.include_router(obligation_breakdowns_router)

# F2-C: Derived intelligence + rollups
router.include_router(intelligence_router)
router.include_router(rollups_router)
