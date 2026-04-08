"""KB routers sub-package — re-exports the merged router."""

from fastapi import APIRouter

from server.app.domains.kb.routers.entries import router as entries_router
from server.app.domains.kb.routers.compilation import router as compilation_router

router = APIRouter(prefix="/api/kb", tags=["kb"])
router.include_router(entries_router)
router.include_router(compilation_router)

__all__ = ["router"]
