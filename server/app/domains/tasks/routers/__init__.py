"""Tasks routers sub-package — re-exports all routers."""

from server.app.domains.tasks.routers.tasks import router
from server.app.domains.tasks.routers.execution_events import events_router

__all__ = [
    "router",
    "events_router",
]
