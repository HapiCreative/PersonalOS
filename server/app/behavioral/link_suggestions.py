"""
Link suggestion service (Section 5.5 — Behavioral Layer).
Generates suggested edges: origin=llm, state=pending_review, real semantic relation_type.
Metadata includes suggestion_rationale + confidence_explanation + supporting_signals.

Invariant D-01: Link suggestions use DerivedExplanation for explainability.
"""

import uuid
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node
from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    EdgeRelationType, EdgeOrigin, EdgeState, PipelineJobType,
)
from server.app.core.services.llm import (
    get_llm_provider, is_llm_available,
    LINK_SUGGESTION_SYSTEM_PROMPT, LINK_SUGGESTION_PROMPT_TEMPLATE,
    PROMPT_VERSION,
)
from server.app.core.services.pipeline import create_pipeline_job, start_job, complete_job, fail_job
from server.app.derived.retrieval_modes import retrieve
from server.app.derived.schemas import DerivedExplanation, DerivedFactor

logger = logging.getLogger(__name__)


# Valid relation types for LLM-suggested edges
ALLOWED_SUGGESTION_TYPES = {
    EdgeRelationType.SEMANTIC_REFERENCE,
    EdgeRelationType.DERIVED_FROM_SOURCE,
    EdgeRelationType.SOURCE_SUPPORTS_GOAL,
    EdgeRelationType.CAPTURED_FOR,
    EdgeRelationType.GOAL_TRACKS_KB,
    EdgeRelationType.SOURCE_QUOTED_IN,
}


async def suggest_links_for_node(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> list[Edge]:
    """
    Generate link suggestions for a node.
    Uses link_suggestion retrieval mode to find candidates,
    then LLM to evaluate relationships.
    Creates edges with origin=llm, state=pending_review.
    """
    # Get the source node
    result = await db.execute(
        select(Node).where(and_(Node.id == node_id, Node.owner_id == owner_id))
    )
    source_node = result.scalar_one_or_none()
    if not source_node:
        return []

    # Create pipeline job for tracking
    job = await create_pipeline_job(
        db, owner_id, PipelineJobType.SUGGEST_LINKS,
        target_node_id=node_id,
        idempotency_key=f"suggest_links:{node_id}:{datetime.now(timezone.utc).date()}",
        prompt_version=PROMPT_VERSION,
    )
    await start_job(db, job.id)

    try:
        # Retrieve candidate nodes using link_suggestion mode
        candidates = await retrieve(db, owner_id, "link_suggestion", limit=10)
        # Filter out self and already-linked nodes
        existing_edges = await db.execute(
            select(Edge.target_id).where(
                and_(Edge.source_id == node_id, Edge.state != EdgeState.DISMISSED)
            )
        )
        existing_target_ids = {r[0] for r in existing_edges.fetchall()}

        # Also get edges where this node is the target
        reverse_edges = await db.execute(
            select(Edge.source_id).where(
                and_(Edge.target_id == node_id, Edge.state != EdgeState.DISMISSED)
            )
        )
        existing_source_ids = {r[0] for r in reverse_edges.fetchall()}
        already_linked = existing_target_ids | existing_source_ids | {node_id}

        filtered_candidates = [c for c in candidates if c.node_id not in already_linked]

        if not filtered_candidates:
            await complete_job(db, job.id, {"suggestions": 0})
            return []

        suggested_edges = []

        if is_llm_available():
            # Format candidates for LLM
            candidate_text = "\n".join(
                f"- ID: {c.node_id}, Type: {c.node_type}, Title: {c.title}"
                f"{', Summary: ' + c.summary if c.summary else ''}"
                for c in filtered_candidates
            )

            prompt = LINK_SUGGESTION_PROMPT_TEMPLATE.format(
                source_title=source_node.title,
                source_type=source_node.type.value,
                source_summary=source_node.summary or "",
                candidates=candidate_text,
            )

            provider = get_llm_provider()
            response = await provider.complete_json(
                prompt, system_prompt=LINK_SUGGESTION_SYSTEM_PROMPT
            )

            suggestions = response if isinstance(response, list) else response.get("suggestions", []) if isinstance(response, dict) else []

            for suggestion in suggestions:
                target_node_id = suggestion.get("target_node_id")
                relation_type_str = suggestion.get("relation_type", "semantic_reference")
                confidence = float(suggestion.get("confidence", 0.5))
                rationale = suggestion.get("rationale", "")

                # Validate relation type
                try:
                    relation_type = EdgeRelationType(relation_type_str)
                except ValueError:
                    relation_type = EdgeRelationType.SEMANTIC_REFERENCE

                if relation_type not in ALLOWED_SUGGESTION_TYPES:
                    relation_type = EdgeRelationType.SEMANTIC_REFERENCE

                # Parse target_node_id
                try:
                    target_uuid = uuid.UUID(str(target_node_id))
                except (ValueError, TypeError):
                    continue

                # Invariant D-01: Build DerivedExplanation for the suggestion
                explanation = DerivedExplanation(
                    summary=rationale or f"AI detected a {relation_type.value} relationship.",
                    factors=[
                        DerivedFactor(signal="semantic_similarity", value=confidence, weight=0.6),
                        DerivedFactor(signal="relation_type_match", value=relation_type.value, weight=0.4),
                    ],
                    confidence=confidence,
                    generated_at=datetime.now(timezone.utc),
                    version=PROMPT_VERSION,
                )

                # Create edge with origin=llm, state=pending_review
                edge = Edge(
                    source_id=node_id,
                    target_id=target_uuid,
                    relation_type=relation_type,
                    origin=EdgeOrigin.LLM,
                    state=EdgeState.PENDING_REVIEW,
                    weight=1.0,
                    confidence=confidence,
                    metadata_={
                        "suggestion_rationale": rationale,
                        "confidence_explanation": explanation.to_dict(),
                        "supporting_signals": [
                            {"signal": f.signal, "value": f.value}
                            for f in explanation.factors
                        ],
                    },
                )
                db.add(edge)
                suggested_edges.append(edge)

        else:
            # Graceful degradation: suggest top candidates as semantic_reference
            for candidate in filtered_candidates[:3]:
                explanation = DerivedExplanation(
                    summary=f"Potentially related based on content similarity.",
                    factors=[
                        DerivedFactor(signal="combined_score", value=candidate.combined_score, weight=1.0),
                    ],
                    confidence=candidate.combined_score,
                    generated_at=datetime.now(timezone.utc),
                    version="heuristic-v1",
                )

                edge = Edge(
                    source_id=node_id,
                    target_id=candidate.node_id,
                    relation_type=EdgeRelationType.SEMANTIC_REFERENCE,
                    origin=EdgeOrigin.LLM,
                    state=EdgeState.PENDING_REVIEW,
                    weight=1.0,
                    confidence=candidate.combined_score,
                    metadata_={
                        "suggestion_rationale": f"Content similarity score: {candidate.combined_score:.2f}",
                        "confidence_explanation": explanation.to_dict(),
                        "supporting_signals": [
                            {"signal": "combined_score", "value": candidate.combined_score},
                        ],
                    },
                )
                db.add(edge)
                suggested_edges.append(edge)

        await db.flush()
        await complete_job(db, job.id, {"suggestions": len(suggested_edges)})
        return suggested_edges

    except Exception as e:
        logger.exception(f"Failed to generate link suggestions for node {node_id}")
        await fail_job(db, job.id, str(e))
        return []
