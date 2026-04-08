"""Goals domain schemas — re-exports all schema classes."""

from server.app.domains.goals.schemas.goals import (
    GoalCreate,
    GoalListResponse,
    GoalResponse,
    GoalUpdate,
)
from server.app.domains.goals.schemas.linked_tasks import (
    GoalLinkedTaskResponse,
    GoalWithTasksResponse,
)

__all__ = [
    "GoalCreate",
    "GoalLinkedTaskResponse",
    "GoalListResponse",
    "GoalResponse",
    "GoalUpdate",
    "GoalWithTasksResponse",
]
