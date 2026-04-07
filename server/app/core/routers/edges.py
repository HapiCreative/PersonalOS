"""
Edge router (Section 8.3).
Endpoints: POST /api/edges, GET /api/nodes/{id}/edges
Layer: Core (link)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import EdgeRelationType, EdgeState
from server.app.core.schemas.edge import EdgeCreate, EdgeListResponse, EdgeResponse, EdgeStateUpdate
from server.app.core.services.edge_service import (
    create_edge,
    delete_edge,
    get_edges_for_node,
    update_edge_state,
)

router = APIRouter(tags=["edges"])


@router.post("/api/edges", response_model=EdgeResponse, status_code=status.HTTP_201_CREATED)
async def create_edge_endpoint(
    body: EdgeCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create an edge between two nodes.
    Validates: G-01 (type-pair), G-02 (semantic_reference), G-03 (same owner).
    """
    try:
        edge = await create_edge(
            db,
            user.id,
            body.source_id,
            body.target_id,
            body.relation_type,
            body.origin,
            body.state,
            body.weight,
            body.confidence,
            body.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    return EdgeResponse(
        id=edge.id,
        source_id=edge.source_id,
        target_id=edge.target_id,
        relation_type=edge.relation_type,
        origin=edge.origin,
        state=edge.state,
        weight=edge.weight,
        confidence=edge.confidence,
        metadata=edge.metadata_,
        created_at=edge.created_at,
    )


@router.get("/api/nodes/{node_id}/edges", response_model=EdgeListResponse)
async def get_node_edges_endpoint(
    node_id: uuid.UUID,
    direction: str = Query(default="both", pattern="^(outgoing|incoming|both)$"),
    relation_type: EdgeRelationType | None = None,
    state: EdgeState | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get edges for a node, with optional filters."""
    try:
        edges = await get_edges_for_node(db, user.id, node_id, direction, relation_type, state)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    items = [
        EdgeResponse(
            id=e.id,
            source_id=e.source_id,
            target_id=e.target_id,
            relation_type=e.relation_type,
            origin=e.origin,
            state=e.state,
            weight=e.weight,
            confidence=e.confidence,
            metadata=e.metadata_,
            created_at=e.created_at,
        )
        for e in edges
    ]
    return EdgeListResponse(items=items, total=len(items))


@router.delete("/api/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_edge_endpoint(
    edge_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an edge."""
    success = await delete_edge(db, user.id, edge_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge not found")


@router.patch("/api/edges/{edge_id}/state", response_model=EdgeResponse)
async def update_edge_state_endpoint(
    edge_id: uuid.UUID,
    body: EdgeStateUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update edge state (e.g., accept or dismiss a suggested link).
    Phase 5: Used for one-click promotion of suggested links in context layer.
    """
    edge = await update_edge_state(db, user.id, edge_id, body.state)
    if edge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge not found")

    return EdgeResponse(
        id=edge.id,
        source_id=edge.source_id,
        target_id=edge.target_id,
        relation_type=edge.relation_type,
        origin=edge.origin,
        state=edge.state,
        weight=edge.weight,
        confidence=edge.confidence,
        metadata=edge.metadata_,
        created_at=edge.created_at,
    )
