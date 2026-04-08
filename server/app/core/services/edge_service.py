"""
Edge CRUD service with full constraint validation.
Invariants: G-01, G-02, G-03, G-04.
"""

import uuid

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.edge import Edge
from server.app.core.models.node import Node
from server.app.core.models.enums import EdgeRelationType, EdgeOrigin, EdgeState
from server.app.core.services.graph import validate_edge_type_pair


async def create_edge(
    db: AsyncSession,
    owner_id: uuid.UUID,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    relation_type: EdgeRelationType,
    origin: EdgeOrigin = EdgeOrigin.USER,
    state: EdgeState = EdgeState.ACTIVE,
    weight: float = 1.0,
    confidence: float | None = None,
    metadata: dict | None = None,
) -> Edge:
    """
    Create an edge with full validation.
    Invariant G-01: Edge type-pair constraints (application layer, primary).
    Invariant G-02: semantic_reference specificity.
    Invariant G-03: Same-owner edge constraint.
    """
    # Fetch source and target nodes, enforcing ownership
    source = await db.execute(
        select(Node).where(Node.id == source_id, Node.owner_id == owner_id)
    )
    source_node = source.scalar_one_or_none()
    if source_node is None:
        raise ValueError(f"Source node {source_id} not found or not owned by user")

    target = await db.execute(
        select(Node).where(Node.id == target_id, Node.owner_id == owner_id)
    )
    target_node = target.scalar_one_or_none()
    if target_node is None:
        raise ValueError(f"Target node {target_id} not found or not owned by user")

    # Invariant G-03: Same-owner edge constraint
    if source_node.owner_id != target_node.owner_id:
        raise ValueError("Invariant G-03: Edges must connect nodes with the same owner")

    # Invariant G-01 + G-02: Type-pair validation (application layer, primary)
    error = validate_edge_type_pair(relation_type, source_node.type, target_node.type)
    if error:
        raise ValueError(error)

    edge = Edge(
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        origin=origin,
        state=state,
        weight=weight,
        confidence=confidence,
        metadata_=metadata or {},
    )
    db.add(edge)
    await db.flush()
    return edge


async def get_edges_for_node(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    direction: str = "both",
    relation_type: EdgeRelationType | None = None,
    state: EdgeState | None = None,
) -> list[Edge]:
    """
    Get edges for a node, enforcing ownership via the node.
    direction: 'outgoing', 'incoming', or 'both'.
    """
    # Verify node ownership
    node = await db.execute(
        select(Node).where(Node.id == node_id, Node.owner_id == owner_id)
    )
    if node.scalar_one_or_none() is None:
        raise ValueError(f"Node {node_id} not found or not owned by user")

    filters = []
    if direction == "outgoing":
        filters.append(Edge.source_id == node_id)
    elif direction == "incoming":
        filters.append(Edge.target_id == node_id)
    else:
        filters.append(or_(Edge.source_id == node_id, Edge.target_id == node_id))

    if relation_type:
        filters.append(Edge.relation_type == relation_type)
    if state:
        filters.append(Edge.state == state)

    stmt = select(Edge).where(*filters).order_by(Edge.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_edge(
    db: AsyncSession,
    owner_id: uuid.UUID,
    edge_id: uuid.UUID,
) -> bool:
    """Delete an edge, verifying ownership through source node."""
    stmt = (
        select(Edge)
        .join(Node, Node.id == Edge.source_id)
        .where(Edge.id == edge_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    edge = result.scalar_one_or_none()
    if edge is None:
        return False

    await db.delete(edge)
    await db.flush()
    return True


async def update_edge_state(
    db: AsyncSession,
    owner_id: uuid.UUID,
    edge_id: uuid.UUID,
    new_state: EdgeState,
) -> Edge | None:
    """Update edge state (e.g., accept/dismiss a suggested link)."""
    stmt = (
        select(Edge)
        .join(Node, Node.id == Edge.source_id)
        .where(Edge.id == edge_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    edge = result.scalar_one_or_none()
    if edge is None:
        return None

    edge.state = new_state
    await db.flush()
    return edge


async def update_edge_weight(
    db: AsyncSession,
    owner_id: uuid.UUID,
    edge_id: uuid.UUID,
    new_weight: float,
) -> Edge | None:
    """
    Phase PB: User override of edge weight.
    Section 2.3 Edge Weight Rules:
    - Post-MVP (Phase B): Users can optionally adjust weights.
    - Weight must be 0.0-1.0 (enforced by DB constraint edges_weight_range).
    """
    if not (0.0 <= new_weight <= 1.0):
        raise ValueError("Edge weight must be between 0.0 and 1.0")

    stmt = (
        select(Edge)
        .join(Node, Node.id == Edge.source_id)
        .where(Edge.id == edge_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    edge = result.scalar_one_or_none()
    if edge is None:
        return None

    edge.weight = new_weight
    await db.flush()
    return edge
