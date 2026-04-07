"""
Phase 10: Export/import for all Core entities (JSON format, preserving edges).
Section 1.1: Core entities are exportable.
Section 1.7: User-owned data — never auto-delete, always exportable.

Export format: JSON with all Core entities + edges + companion table data.
Import: Creates new nodes/edges, preserving relationships via ID mapping.
"""

import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import (
    Node, InboxItem, TaskNode, JournalNode,
    SourceItemNode, SourceFragment, KBNode, MemoryNode,
    GoalNode, ProjectNode, NodeEnrichment,
)
from server.app.core.models.edge import Edge
from server.app.core.models.enums import NodeType

logger = logging.getLogger(__name__)

# Export version for forward compatibility
EXPORT_FORMAT_VERSION = "1.0"


async def export_all(
    db: AsyncSession,
    owner_id: uuid.UUID,
    include_archived: bool = True,
    include_enrichments: bool = True,
) -> dict:
    """
    Export all Core entities for a user as a JSON-serializable dict.
    Section 1.1: Core entities are exportable.

    Structure:
    {
        "version": "1.0",
        "exported_at": "...",
        "nodes": [...],
        "edges": [...],
        "enrichments": [...]
    }
    """
    # Fetch all nodes
    node_filters = [Node.owner_id == owner_id]
    if not include_archived:
        node_filters.append(Node.archived_at.is_(None))

    nodes_stmt = select(Node).where(*node_filters).order_by(Node.created_at)
    nodes_result = await db.execute(nodes_stmt)
    nodes = list(nodes_result.scalars().all())

    node_ids = [n.id for n in nodes]
    node_id_set = set(node_ids)

    # Export companion table data for each node
    exported_nodes = []
    for node in nodes:
        node_data = _serialize_node(node)

        # Fetch companion table data based on type
        companion = await _get_companion_data(db, node)
        if companion:
            node_data["companion"] = companion

        exported_nodes.append(node_data)

    # Fetch all edges between owned nodes
    edges_stmt = select(Edge).where(
        and_(
            Edge.source_id.in_(node_ids),
            Edge.target_id.in_(node_ids),
        )
    ).order_by(Edge.created_at)
    edges_result = await db.execute(edges_stmt)
    edges = list(edges_result.scalars().all())

    exported_edges = [_serialize_edge(e) for e in edges]

    # Optionally export enrichments
    exported_enrichments = []
    if include_enrichments:
        enrich_stmt = (
            select(NodeEnrichment)
            .where(NodeEnrichment.node_id.in_(node_ids))
            .order_by(NodeEnrichment.created_at)
        )
        enrich_result = await db.execute(enrich_stmt)
        enrichments = list(enrich_result.scalars().all())
        exported_enrichments = [_serialize_enrichment(e) for e in enrichments]

    return {
        "version": EXPORT_FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "owner_id": str(owner_id),
        "node_count": len(exported_nodes),
        "edge_count": len(exported_edges),
        "enrichment_count": len(exported_enrichments),
        "nodes": exported_nodes,
        "edges": exported_edges,
        "enrichments": exported_enrichments,
    }


async def import_all(
    db: AsyncSession,
    owner_id: uuid.UUID,
    data: dict,
    merge_strategy: str = "skip_existing",
) -> dict:
    """
    Import Core entities from an export payload.
    Creates new nodes/edges, mapping old IDs to new IDs.

    merge_strategy:
      - "skip_existing": Skip nodes that already exist (by title+type match)
      - "create_new": Always create new nodes with new IDs

    Returns summary of what was imported.
    """
    if data.get("version") != EXPORT_FORMAT_VERSION:
        raise ValueError(
            f"Unsupported export format version: {data.get('version')}. "
            f"Expected: {EXPORT_FORMAT_VERSION}"
        )

    id_map: dict[str, uuid.UUID] = {}  # old_id -> new_id
    nodes_created = 0
    nodes_skipped = 0
    edges_created = 0
    edges_skipped = 0
    enrichments_created = 0
    errors: list[str] = []

    # Phase 1: Import nodes
    for node_data in data.get("nodes", []):
        try:
            old_id = node_data["id"]

            # Check for existing node with same title+type if merging
            if merge_strategy == "skip_existing":
                existing = await db.execute(
                    select(Node).where(
                        and_(
                            Node.owner_id == owner_id,
                            Node.title == node_data["title"],
                            Node.type == node_data["type"],
                        )
                    )
                )
                existing_node = existing.scalar_one_or_none()
                if existing_node:
                    id_map[old_id] = existing_node.id
                    nodes_skipped += 1
                    continue

            # Create new node
            new_node = Node(
                type=node_data["type"],
                owner_id=owner_id,
                title=node_data["title"],
                summary=node_data.get("summary"),
            )
            db.add(new_node)
            await db.flush()

            id_map[old_id] = new_node.id

            # Create companion table record
            companion = node_data.get("companion")
            if companion:
                await _create_companion(db, new_node, companion)

            nodes_created += 1

        except Exception as e:
            logger.warning("Import error for node %s: %s", node_data.get("id"), e)
            errors.append(f"Node import error: {e}")

    # Phase 2: Import edges (after all nodes exist)
    for edge_data in data.get("edges", []):
        try:
            old_source = edge_data["source_id"]
            old_target = edge_data["target_id"]

            # Map old IDs to new IDs
            new_source = id_map.get(old_source)
            new_target = id_map.get(old_target)

            if not new_source or not new_target:
                edges_skipped += 1
                continue

            # Check for duplicate edge
            existing_edge = await db.execute(
                select(Edge).where(
                    and_(
                        Edge.source_id == new_source,
                        Edge.target_id == new_target,
                        Edge.relation_type == edge_data["relation_type"],
                    )
                )
            )
            if existing_edge.scalar_one_or_none():
                edges_skipped += 1
                continue

            new_edge = Edge(
                source_id=new_source,
                target_id=new_target,
                relation_type=edge_data["relation_type"],
                origin=edge_data.get("origin", "user"),
                state=edge_data.get("state", "active"),
                weight=edge_data.get("weight", 1.0),
                confidence=edge_data.get("confidence"),
                metadata_=edge_data.get("metadata", {}),
            )
            db.add(new_edge)
            await db.flush()
            edges_created += 1

        except Exception as e:
            logger.warning("Import error for edge: %s", e)
            errors.append(f"Edge import error: {e}")

    # Phase 3: Import enrichments
    for enrich_data in data.get("enrichments", []):
        try:
            old_node_id = enrich_data["node_id"]
            new_node_id = id_map.get(old_node_id)

            if not new_node_id:
                continue

            new_enrichment = NodeEnrichment(
                node_id=new_node_id,
                enrichment_type=enrich_data["enrichment_type"],
                payload=enrich_data.get("payload", {}),
                status=enrich_data.get("status", "completed"),
                prompt_version=enrich_data.get("prompt_version"),
                model_version=enrich_data.get("model_version"),
            )
            db.add(new_enrichment)
            await db.flush()
            enrichments_created += 1

        except Exception as e:
            logger.warning("Import error for enrichment: %s", e)
            errors.append(f"Enrichment import error: {e}")

    return {
        "nodes_created": nodes_created,
        "nodes_skipped": nodes_skipped,
        "edges_created": edges_created,
        "edges_skipped": edges_skipped,
        "enrichments_created": enrichments_created,
        "errors": errors,
        "id_mapping": {k: str(v) for k, v in id_map.items()},
    }


# =============================================================================
# Serialization helpers
# =============================================================================


def _serialize_node(node: Node) -> dict:
    """Serialize a node to JSON-safe dict."""
    return {
        "id": str(node.id),
        "type": node.type.value if hasattr(node.type, "value") else str(node.type),
        "title": node.title,
        "summary": node.summary,
        "created_at": node.created_at.isoformat() if node.created_at else None,
        "updated_at": node.updated_at.isoformat() if node.updated_at else None,
        "archived_at": node.archived_at.isoformat() if node.archived_at else None,
        "last_accessed_at": node.last_accessed_at.isoformat() if node.last_accessed_at else None,
    }


def _serialize_edge(edge: Edge) -> dict:
    """Serialize an edge to JSON-safe dict."""
    return {
        "id": str(edge.id),
        "source_id": str(edge.source_id),
        "target_id": str(edge.target_id),
        "relation_type": edge.relation_type.value if hasattr(edge.relation_type, "value") else str(edge.relation_type),
        "origin": edge.origin.value if hasattr(edge.origin, "value") else str(edge.origin),
        "state": edge.state.value if hasattr(edge.state, "value") else str(edge.state),
        "weight": edge.weight,
        "confidence": edge.confidence,
        "metadata": edge.metadata_ if edge.metadata_ else {},
        "created_at": edge.created_at.isoformat() if edge.created_at else None,
    }


def _serialize_enrichment(enrichment: NodeEnrichment) -> dict:
    """Serialize a node enrichment to JSON-safe dict."""
    return {
        "id": str(enrichment.id),
        "node_id": str(enrichment.node_id),
        "enrichment_type": enrichment.enrichment_type.value if hasattr(enrichment.enrichment_type, "value") else str(enrichment.enrichment_type),
        "payload": enrichment.payload,
        "status": enrichment.status.value if hasattr(enrichment.status, "value") else str(enrichment.status),
        "prompt_version": enrichment.prompt_version,
        "model_version": enrichment.model_version,
        "superseded_at": enrichment.superseded_at.isoformat() if enrichment.superseded_at else None,
        "created_at": enrichment.created_at.isoformat() if enrichment.created_at else None,
    }


# =============================================================================
# Companion table serialization/deserialization
# =============================================================================


async def _get_companion_data(db: AsyncSession, node: Node) -> dict | None:
    """Fetch and serialize companion table data for a node."""
    node_type = node.type.value if hasattr(node.type, "value") else str(node.type)

    if node_type == "inbox_item":
        result = await db.execute(
            select(InboxItem).where(InboxItem.node_id == node.id)
        )
        companion = result.scalar_one_or_none()
        if companion:
            return {
                "raw_text": companion.raw_text,
                "status": companion.status.value if hasattr(companion.status, "value") else str(companion.status),
            }

    elif node_type == "task":
        result = await db.execute(
            select(TaskNode).where(TaskNode.node_id == node.id)
        )
        companion = result.scalar_one_or_none()
        if companion:
            return {
                "status": companion.status.value if hasattr(companion.status, "value") else str(companion.status),
                "priority": companion.priority.value if hasattr(companion.priority, "value") else str(companion.priority),
                "due_date": companion.due_date.isoformat() if companion.due_date else None,
                "recurrence": companion.recurrence,
                "is_recurring": companion.is_recurring,
                "notes": companion.notes,
            }

    elif node_type == "journal_entry":
        result = await db.execute(
            select(JournalNode).where(JournalNode.node_id == node.id)
        )
        companion = result.scalar_one_or_none()
        if companion:
            return {
                "content": companion.content,
                "entry_date": companion.entry_date.isoformat() if companion.entry_date else None,
                "mood": companion.mood.value if companion.mood and hasattr(companion.mood, "value") else (str(companion.mood) if companion.mood else None),
                "tags": companion.tags or [],
                "word_count": companion.word_count,
            }

    elif node_type == "source_item":
        result = await db.execute(
            select(SourceItemNode).where(SourceItemNode.node_id == node.id)
        )
        companion = result.scalar_one_or_none()
        if companion:
            data = {
                "source_type": companion.source_type.value if hasattr(companion.source_type, "value") else str(companion.source_type),
                "url": companion.url,
                "author": companion.author,
                "platform": companion.platform,
                "published_at": companion.published_at.isoformat() if companion.published_at else None,
                "capture_context": companion.capture_context,
                "raw_content": companion.raw_content,
                "canonical_content": companion.canonical_content,
                "processing_status": companion.processing_status.value if hasattr(companion.processing_status, "value") else str(companion.processing_status),
                "triage_status": companion.triage_status.value if hasattr(companion.triage_status, "value") else str(companion.triage_status),
                "permanence": companion.permanence.value if hasattr(companion.permanence, "value") else str(companion.permanence),
                "checksum": companion.checksum,
            }

            # Also export fragments
            frags_result = await db.execute(
                select(SourceFragment)
                .where(SourceFragment.source_node_id == node.id)
                .order_by(SourceFragment.position)
            )
            fragments = list(frags_result.scalars().all())
            if fragments:
                data["fragments"] = [
                    {
                        "fragment_text": f.fragment_text,
                        "position": f.position,
                        "fragment_type": f.fragment_type.value if hasattr(f.fragment_type, "value") else str(f.fragment_type),
                        "section_ref": f.section_ref,
                    }
                    for f in fragments
                ]

            return data

    elif node_type == "kb_entry":
        result = await db.execute(
            select(KBNode).where(KBNode.node_id == node.id)
        )
        companion = result.scalar_one_or_none()
        if companion:
            return {
                "content": companion.content,
                "raw_content": companion.raw_content,
                "compile_status": companion.compile_status.value if hasattr(companion.compile_status, "value") else str(companion.compile_status),
                "pipeline_stage": companion.pipeline_stage.value if hasattr(companion.pipeline_stage, "value") else str(companion.pipeline_stage),
                "tags": companion.tags or [],
                "compile_version": companion.compile_version,
            }

    elif node_type == "memory":
        result = await db.execute(
            select(MemoryNode).where(MemoryNode.node_id == node.id)
        )
        companion = result.scalar_one_or_none()
        if companion:
            return {
                "memory_type": companion.memory_type.value if hasattr(companion.memory_type, "value") else str(companion.memory_type),
                "content": companion.content,
                "context": companion.context,
                "review_at": companion.review_at.isoformat() if companion.review_at else None,
                "tags": companion.tags or [],
            }

    elif node_type == "goal":
        result = await db.execute(
            select(GoalNode).where(GoalNode.node_id == node.id)
        )
        companion = result.scalar_one_or_none()
        if companion:
            return {
                "status": companion.status.value if hasattr(companion.status, "value") else str(companion.status),
                "start_date": companion.start_date.isoformat() if companion.start_date else None,
                "end_date": companion.end_date.isoformat() if companion.end_date else None,
                "timeframe_label": companion.timeframe_label,
                "progress": companion.progress,
                "milestones": companion.milestones or [],
                "notes": companion.notes,
            }

    elif node_type == "project":
        result = await db.execute(
            select(ProjectNode).where(ProjectNode.node_id == node.id)
        )
        companion = result.scalar_one_or_none()
        if companion:
            return {
                "status": companion.status.value if hasattr(companion.status, "value") else str(companion.status),
                "description": companion.description,
                "tags": companion.tags or [],
            }

    return None


async def _create_companion(db: AsyncSession, node: Node, companion: dict) -> None:
    """Create companion table record from import data."""
    node_type = node.type.value if hasattr(node.type, "value") else str(node.type)

    if node_type == "inbox_item":
        item = InboxItem(
            node_id=node.id,
            raw_text=companion.get("raw_text", ""),
            status=companion.get("status", "pending"),
        )
        db.add(item)

    elif node_type == "task":
        item = TaskNode(
            node_id=node.id,
            status=companion.get("status", "todo"),
            priority=companion.get("priority", "medium"),
            due_date=companion.get("due_date"),
            recurrence=companion.get("recurrence"),
            is_recurring=companion.get("is_recurring", False),
            notes=companion.get("notes"),
        )
        db.add(item)

    elif node_type == "journal_entry":
        item = JournalNode(
            node_id=node.id,
            content=companion.get("content", ""),
            entry_date=companion.get("entry_date", datetime.now(timezone.utc).date()),
            mood=companion.get("mood"),
            tags=companion.get("tags", []),
            word_count=companion.get("word_count", 0),
        )
        db.add(item)

    elif node_type == "source_item":
        item = SourceItemNode(
            node_id=node.id,
            source_type=companion.get("source_type", "other"),
            url=companion.get("url"),
            author=companion.get("author"),
            platform=companion.get("platform"),
            capture_context=companion.get("capture_context"),
            raw_content=companion.get("raw_content", ""),
            canonical_content=companion.get("canonical_content"),
            processing_status=companion.get("processing_status", "raw"),
            triage_status=companion.get("triage_status", "unreviewed"),
            permanence=companion.get("permanence", "reference"),
            checksum=companion.get("checksum"),
        )
        db.add(item)
        await db.flush()

        # Create fragments if present
        for frag_data in companion.get("fragments", []):
            frag = SourceFragment(
                source_node_id=node.id,
                fragment_text=frag_data.get("fragment_text", ""),
                position=frag_data.get("position", 0),
                fragment_type=frag_data.get("fragment_type", "paragraph"),
                section_ref=frag_data.get("section_ref"),
            )
            db.add(frag)

    elif node_type == "kb_entry":
        item = KBNode(
            node_id=node.id,
            content=companion.get("content", ""),
            raw_content=companion.get("raw_content"),
            compile_status=companion.get("compile_status", "ingest"),
            pipeline_stage=companion.get("pipeline_stage", "draft"),
            tags=companion.get("tags", []),
            compile_version=companion.get("compile_version", 0),
        )
        db.add(item)

    elif node_type == "memory":
        item = MemoryNode(
            node_id=node.id,
            memory_type=companion.get("memory_type", "insight"),
            content=companion.get("content", ""),
            context=companion.get("context"),
            review_at=companion.get("review_at"),
            tags=companion.get("tags", []),
        )
        db.add(item)

    elif node_type == "goal":
        item = GoalNode(
            node_id=node.id,
            status=companion.get("status", "active"),
            start_date=companion.get("start_date"),
            end_date=companion.get("end_date"),
            timeframe_label=companion.get("timeframe_label"),
            progress=companion.get("progress", 0.0),
            milestones=companion.get("milestones", []),
            notes=companion.get("notes"),
        )
        db.add(item)

    elif node_type == "project":
        item = ProjectNode(
            node_id=node.id,
            status=companion.get("status", "active"),
            description=companion.get("description"),
            tags=companion.get("tags", []),
        )
        db.add(item)

    await db.flush()
