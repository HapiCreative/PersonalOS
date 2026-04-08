"""Inbox routers sub-package. Re-exports the merged router."""

from server.app.domains.inbox.routers.inbox_items import router

__all__ = ["router"]
