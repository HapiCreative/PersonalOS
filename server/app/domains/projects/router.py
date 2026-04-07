"""
Projects domain router (Section 8.3).
Endpoints: POST/GET /api/projects, GET /api/projects/{id}, PUT /api/projects/{id}
Layer: Core (read/write)

Invariant G-05: belongs_to edges restricted to goal→project, task→project.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import ProjectStatus
from server.app.domains.projects.schemas import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    ProjectWithLinksResponse,
    ProjectLinkedItemResponse,
)
from server.app.domains.projects.service import (
    create_project,
    get_project,
    list_projects,
    update_project,
    get_project_linked_items,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _to_response(node, project) -> ProjectResponse:
    return ProjectResponse(
        node_id=node.id,
        title=node.title,
        summary=node.summary,
        status=project.status,
        description=project.description,
        tags=project.tags if isinstance(project.tags, list) else [],
        created_at=node.created_at,
        updated_at=node.updated_at,
        archived_at=node.archived_at,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project_endpoint(
    body: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project."""
    node, project = await create_project(
        db, user.id, body.title, body.summary,
        body.status, body.description, body.tags,
    )
    return _to_response(node, project)


@router.get("", response_model=ProjectListResponse)
async def list_projects_endpoint(
    status_filter: ProjectStatus | None = Query(default=None, alias="status"),
    include_archived: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List projects with optional filters."""
    items, total = await list_projects(
        db, user.id, status_filter, include_archived, limit, offset,
    )
    return ProjectListResponse(
        items=[_to_response(n, p) for n, p in items],
        total=total,
    )


@router.get("/{node_id}", response_model=ProjectWithLinksResponse)
async def get_project_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single project by node ID, including linked goals/tasks."""
    pair = await get_project(db, user.id, node_id)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    node, project = pair
    linked_items = await get_project_linked_items(db, user.id, node_id)

    resp = ProjectWithLinksResponse(
        **_to_response(node, project).model_dump(),
        linked_items=[ProjectLinkedItemResponse(**item) for item in linked_items],
    )
    return resp


@router.put("/{node_id}", response_model=ProjectResponse)
async def update_project_endpoint(
    node_id: uuid.UUID,
    body: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update project fields."""
    pair = await update_project(
        db, user.id, node_id,
        title=body.title,
        summary=body.summary,
        status=body.status,
        description=body.description if body.description is not None else ...,
        tags=body.tags,
    )
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return _to_response(*pair)
