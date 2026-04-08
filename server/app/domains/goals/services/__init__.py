"""Goals domain services — re-exports all public functions."""

from server.app.domains.goals.services.goals import (
    create_goal,
    get_goal,
    get_goal_linked_tasks,
    list_goals,
    update_goal,
)
from server.app.domains.goals.services.progress import (
    compute_goal_progress,
    refresh_goal_progress,
)

__all__ = [
    "compute_goal_progress",
    "create_goal",
    "get_goal",
    "get_goal_linked_tasks",
    "list_goals",
    "refresh_goal_progress",
    "update_goal",
]
