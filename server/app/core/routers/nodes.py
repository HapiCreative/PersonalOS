"""
Node CRUD router (Section 8.3).
Endpoints: GET/POST/PUT/DELETE /api/nodes/{id}
Layer: Core (read/write)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import NodeType
from server.app.core.schemas.node import NodeCreate, NodeListResponse, NodeResponse, NodeUpdate
from server.app.core.services.node_service import (
    create_node,
    get_node,
    hard_delete_node,
    list_nodes,
    restore_node,
    soft_delete_node,
    update_node,
)

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


@router.post("", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
async def create_node_endpoint(
    body: NodeCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new Core node."""
    node = await create_node(db, user.id, body.type, body.title, body.summary)
    return NodeResponse.model_validate(node)


@router.get("", response_model=NodeListResponse)
async def list_nodes_endpoint(
    type: NodeType | None = None,
    include_archived: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List nodes, filtered by type. Ownership enforced at query layer."""
    nodes, total = await list_nodes(db, user.id, type, include_archived, limit, offset)
    return NodeListResponse(
        items=[NodeResponse.model_validate(n) for n in nodes],
        total=total,
    )


@router.get("/{node_id}", response_model=NodeResponse)
async def get_node_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single node by ID. Updates last_accessed_at."""
    node = await get_node(db, user.id, node_id)
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return NodeResponse.model_validate(node)


@router.put("/{node_id}", response_model=NodeResponse)
async def update_node_endpoint(
    node_id: uuid.UUID,
    body: NodeUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update node fields. Last-write-wins (Section 1.8)."""
    node = await update_node(db, user.id, node_id, body.title, body.summary)
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return NodeResponse.model_validate(node)


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node_endpoint(
    node_id: uuid.UUID,
    permanent: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a node.
    Default: soft delete (sets archived_at). Reversible.
    permanent=true: hard delete with cascade (Invariant B-02). Irreversible.
    """
    if permanent:
        success = await hard_delete_node(db, user.id, node_id)
    else:
        result = await soft_delete_node(db, user.id, node_id)
        success = result is not None

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")


@router.post("/{node_id}/restore", response_model=NodeResponse)
async def restore_node_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Restore a soft-deleted node."""
    node = await restore_node(db, user.id, node_id)
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archived node not found")
    return NodeResponse.model_validate(node)
