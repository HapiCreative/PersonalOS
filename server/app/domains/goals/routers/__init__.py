"""Goals domain routers — re-exports the merged router."""

from fastapi import APIRouter

from server.app.domains.goals.routers.goals import router as _goals_router
from server.app.domains.goals.routers.progress import router as _progress_router

router = APIRouter()
router.include_router(_goals_router)
router.include_router(_progress_router)

__all__ = ["router"]
