"""
Project linked-items service.
Retrieves goals and tasks linked to a project via belongs_to edges.

Invariant G-05: belongs_to edges restricted to goal->project, task->project.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, GoalNode, TaskNode
from server.app.core.models.edge import Edge
from server.app.core.models.enums import EdgeRelationType, EdgeState


async def get_project_linked_items(
    db: AsyncSession,
    owner_id: uuid.UUID,
    project_node_id: uuid.UUID,
) -> list[dict]:
    """
    Get goals and tasks linked to a project via belongs_to edges.
    Invariant G-05: Only goals and tasks can belong_to a project.
    Returns item info + edge info for display.
    """
    # Query goals linked via belongs_to
    goal_stmt = (
        select(Node, GoalNode, Edge)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .join(Edge, Edge.source_id == Node.id)
        .where(
            Edge.target_id == project_node_id,
            Edge.relation_type == EdgeRelationType.BELONGS_TO,
            Edge.state == EdgeState.ACTIVE,
            Node.owner_id == owner_id,
        )
        .order_by(Node.updated_at.desc())
    )
    goal_result = await db.execute(goal_stmt)
    goal_rows = list(goal_result.all())

    # Query tasks linked via belongs_to
    task_stmt = (
        select(Node, TaskNode, Edge)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .join(Edge, Edge.source_id == Node.id)
        .where(
            Edge.target_id == project_node_id,
            Edge.relation_type == EdgeRelationType.BELONGS_TO,
            Edge.state == EdgeState.ACTIVE,
            Node.owner_id == owner_id,
        )
        .order_by(Node.updated_at.desc())
    )
    task_result = await db.execute(task_stmt)
    task_rows = list(task_result.all())

    items = []
    for node, goal, edge in goal_rows:
        items.append({
            "node_id": node.id,
            "title": node.title,
            "node_type": "goal",
            "status": goal.status.value,
            "edge_id": edge.id,
            "edge_weight": edge.weight,
        })
    for node, task, edge in task_rows:
        items.append({
            "node_id": node.id,
            "title": node.title,
            "node_type": "task",
            "status": task.status.value,
            "edge_id": edge.id,
            "edge_weight": edge.weight,
        })

    return items
