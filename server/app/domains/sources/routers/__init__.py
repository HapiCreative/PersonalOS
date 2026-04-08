"""Sources domain routers — re-exports the merged router."""

from fastapi import APIRouter

from server.app.domains.sources.routers.fragments import router as fragments_router
from server.app.domains.sources.routers.sources import router as sources_router

router = APIRouter()
router.include_router(sources_router)
router.include_router(fragments_router)

__all__ = ["router"]
