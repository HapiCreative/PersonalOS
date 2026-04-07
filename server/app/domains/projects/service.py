"""
Project domain service (Section 2.4, TABLE 19).
Handles project CRUD and linked item retrieval.

Invariant G-05: belongs_to edges restricted to goal→project, task→project.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, ProjectNode, GoalNode, TaskNode
from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    NodeType, ProjectStatus, EdgeRelationType, EdgeState,
)


async def create_project(
    db: AsyncSession,
    owner_id: uuid.UUID,
    title: str,
    summary: str | None = None,
    status: ProjectStatus = ProjectStatus.ACTIVE,
    description: str | None = None,
    tags: list[str] | None = None,
) -> tuple[Node, ProjectNode]:
    """Create a project (Core node + project_nodes companion)."""
    node = Node(
        type=NodeType.PROJECT,
        owner_id=owner_id,
        title=title,
        summary=summary,
    )
    db.add(node)
    await db.flush()

    project = ProjectNode(
        node_id=node.id,
        status=status,
        description=description,
        tags=tags or [],
    )
    db.add(project)
    await db.flush()

    return node, project


async def get_project(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    update_accessed: bool = True,
) -> tuple[Node, ProjectNode] | None:
    """Get a project by node ID, enforcing ownership."""
    stmt = (
        select(Node, ProjectNode)
        .join(ProjectNode, ProjectNode.node_id == Node.id)
        .where(Node.id == node_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None

    node, project = row
    if update_accessed:
        node.last_accessed_at = datetime.now(timezone.utc)
        await db.flush()

    return node, project


async def list_projects(
    db: AsyncSession,
    owner_id: uuid.UUID,
    status: ProjectStatus | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Node, ProjectNode]], int]:
    """List projects with optional filters, enforcing ownership."""
    base_filter = [Node.owner_id == owner_id, Node.type == NodeType.PROJECT]

    if not include_archived:
        base_filter.append(Node.archived_at.is_(None))
    if status:
        base_filter.append(ProjectNode.status == status)

    count_stmt = (
        select(func.count())
        .select_from(Node)
        .join(ProjectNode, ProjectNode.node_id == Node.id)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Node, ProjectNode)
        .join(ProjectNode, ProjectNode.node_id == Node.id)
        .where(*base_filter)
        .order_by(Node.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = list(result.all())

    return items, total


async def update_project(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    title: str | None = None,
    summary: str | None = None,
    status: ProjectStatus | None = None,
    description: str | None = ...,  # type: ignore[assignment]
    tags: list[str] | None = None,
) -> tuple[Node, ProjectNode] | None:
    """Update project fields, enforcing ownership."""
    pair = await get_project(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, project = pair

    if title is not None:
        node.title = title
    if summary is not None:
        node.summary = summary
    if status is not None:
        project.status = status
    if description is not ...:
        project.description = description
    if tags is not None:
        project.tags = tags

    await db.flush()
    return node, project


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
