"""Finance domain routers — merges all entity routers into one."""

from fastapi import APIRouter

from server.app.domains.finance.routers.accounts import router as accounts_router
from server.app.domains.finance.routers.allocations import router as allocations_router
from server.app.domains.finance.routers.balance import router as balance_router
from server.app.domains.finance.routers.categories import router as categories_router
from server.app.domains.finance.routers.csv_import import router as csv_import_router
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
