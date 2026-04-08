"""Journal routers sub-package — re-exports the merged router."""

from server.app.domains.journal.routers.entries import router

__all__ = ["router"]
