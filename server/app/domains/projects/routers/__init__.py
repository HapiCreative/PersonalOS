"""Projects routers sub-package — re-exports all routers."""

from server.app.domains.projects.routers.projects import router

__all__ = [
    "router",
]
