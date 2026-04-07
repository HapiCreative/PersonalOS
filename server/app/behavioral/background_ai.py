"""
Background AI services (Section 5.4, 5.5, 7 — Behavioral Layer).
KB lint pipeline, source auto-enrichment, inbox auto-classification.

These are async behavioral jobs that act on Core and produce Derived outputs.
Rule 3: LLM enriches, never gates. All operations degrade gracefully without AI.
Invariant B-04: Background jobs execute with same ownership scope as interactive requests.
"""

import uuid
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, SourceItemNode, KBNode, InboxItem
from server.app.core.models.enums import (
    NodeType, ProcessingStatus, CompileStatus, InboxItemStatus,
    PipelineJobType, EnrichmentType, EnrichmentStatus,
)
from server.app.core.services.llm import (
    get_llm_provider, is_llm_available,
    ENRICH_SOURCE_SYSTEM_PROMPT, ENRICH_SOURCE_PROMPT_TEMPLATE,
    KB_LINT_SYSTEM_PROMPT, KB_LINT_PROMPT_TEMPLATE,
    CLASSIFY_INBOX_SYSTEM_PROMPT, CLASSIFY_INBOX_PROMPT_TEMPLATE,
    PROMPT_VERSION,
)
from server.app.core.services.pipeline import create_pipeline_job, start_job, complete_job, fail_job
from server.app.derived.enrichments import create_enrichment, complete_enrichment

logger = logging.getLogger(__name__)


async def enrich_source(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> dict:
    """
    Source auto-enrichment via node_enrichments (Section 5.4 Stage 3).
    Generates summary, takeaways, entities using LLM.
    Stores results in node_enrichments table (not flat fields).

    Invariant S-05: One active enrichment per type.
    Invariant B-04: Ownership scope enforced.
    """
    # Verify ownership
    result = await db.execute(
        select(Node, SourceItemNode).join(
            SourceItemNode, Node.id == SourceItemNode.node_id
        ).where(and_(Node.id == node_id, Node.owner_id == owner_id))
    )
    row = result.first()
    if not row:
        return {"error": "Source not found or access denied"}

    node, source = row
    content = source.canonical_content or source.raw_content

    if not content:
        return {"error": "No content to enrich"}

    # Create pipeline job
    job = await create_pipeline_job(
        db, owner_id, PipelineJobType.ENRICH_SOURCE,
        target_node_id=node_id,
        idempotency_key=f"enrich_source:{node_id}:{datetime.now(timezone.utc).date()}",
        prompt_version=PROMPT_VERSION,
    )
    await start_job(db, job.id)

    try:
        if is_llm_available():
            provider = get_llm_provider()
            prompt = ENRICH_SOURCE_PROMPT_TEMPLATE.format(
                title=node.title,
                source_type=source.source_type.value,
                content=content[:4000],  # Limit content length for LLM
            )
            response = await provider.complete_json(prompt, system_prompt=ENRICH_SOURCE_SYSTEM_PROMPT)
            model_version = provider.get_model_version()

            if isinstance(response, dict):
                enrichment_data = response
            else:
                enrichment_data = {"summary": str(response), "takeaways": [], "entities": []}
        else:
            # Graceful degradation
            enrichment_data = {
                "summary": node.summary or content[:200],
                "takeaways": [],
                "entities": [],
            }
            model_version = "noop"

        # Store enrichments in node_enrichments table (Section 4.8)
        results = {}

        # Summary enrichment
        if enrichment_data.get("summary"):
            summary_enrichment = await create_enrichment(
                db, node_id, EnrichmentType.SUMMARY,
                payload={"text": enrichment_data["summary"]},
                status=EnrichmentStatus.COMPLETED,
                prompt_version=PROMPT_VERSION,
                model_version=model_version,
                pipeline_job_id=job.id,
            )
            results["summary"] = str(summary_enrichment.id)

        # Takeaways enrichment
        if enrichment_data.get("takeaways"):
            takeaways_enrichment = await create_enrichment(
                db, node_id, EnrichmentType.TAKEAWAYS,
                payload={"items": enrichment_data["takeaways"]},
                status=EnrichmentStatus.COMPLETED,
                prompt_version=PROMPT_VERSION,
                model_version=model_version,
                pipeline_job_id=job.id,
            )
            results["takeaways"] = str(takeaways_enrichment.id)

        # Entities enrichment
        if enrichment_data.get("entities"):
            entities_enrichment = await create_enrichment(
                db, node_id, EnrichmentType.ENTITIES,
                payload={"items": enrichment_data["entities"]},
                status=EnrichmentStatus.COMPLETED,
                prompt_version=PROMPT_VERSION,
                model_version=model_version,
                pipeline_job_id=job.id,
            )
            results["entities"] = str(entities_enrichment.id)

        # Update processing status
        source.processing_status = ProcessingStatus.ENRICHED

        await complete_job(db, job.id, results)
        return {"status": "enriched", "enrichments": results}

    except Exception as e:
        logger.exception(f"Failed to enrich source {node_id}")
        await fail_job(db, job.id, str(e))
        return {"error": str(e)}


async def lint_kb_entry(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> dict:
    """
    KB lint pipeline (Section 5.5).
    Detects stale KB entries and suggests improvements.
    """
    result = await db.execute(
        select(Node, KBNode).join(
            KBNode, Node.id == KBNode.node_id
        ).where(and_(Node.id == node_id, Node.owner_id == owner_id))
    )
    row = result.first()
    if not row:
        return {"error": "KB entry not found or access denied"}

    node, kb = row

    job = await create_pipeline_job(
        db, owner_id, PipelineJobType.LINT,
        target_node_id=node_id,
        idempotency_key=f"lint_kb:{node_id}:{datetime.now(timezone.utc).date()}",
        prompt_version=PROMPT_VERSION,
    )
    await start_job(db, job.id)

    try:
        if is_llm_available():
            provider = get_llm_provider()
            prompt = KB_LINT_PROMPT_TEMPLATE.format(
                title=node.title,
                content=kb.content[:4000],
                updated_at=node.updated_at.isoformat() if node.updated_at else "unknown",
                compile_status=kb.compile_status.value,
            )
            response = await provider.complete_json(prompt, system_prompt=KB_LINT_SYSTEM_PROMPT)
            model_version = provider.get_model_version()
            lint_result = response if isinstance(response, dict) else {"quality_score": 0.5, "is_stale": False, "issues": [], "suggestions": []}
        else:
            # Heuristic lint without LLM
            days_since_update = 0
            if node.updated_at:
                days_since_update = (datetime.now(timezone.utc) - node.updated_at.replace(tzinfo=timezone.utc)).days
            is_stale = days_since_update > 90 or kb.compile_status == CompileStatus.STALE
            lint_result = {
                "quality_score": 0.5,
                "is_stale": is_stale,
                "issues": ["Content may be outdated"] if is_stale else [],
                "suggestions": ["Review and update content"] if is_stale else [],
            }
            model_version = "heuristic"

        # If stale, update compile_status
        if lint_result.get("is_stale") and kb.compile_status == CompileStatus.ACCEPT:
            kb.compile_status = CompileStatus.STALE

        await complete_job(db, job.id, lint_result)
        return lint_result

    except Exception as e:
        logger.exception(f"Failed to lint KB entry {node_id}")
        await fail_job(db, job.id, str(e))
        return {"error": str(e)}


async def classify_inbox_item(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> dict:
    """
    Inbox auto-classification (Section 5.4 — async behavioral job).
    Determines what type of Core entity an inbox item should become.
    """
    result = await db.execute(
        select(Node, InboxItem).join(
            InboxItem, Node.id == InboxItem.node_id
        ).where(and_(Node.id == node_id, Node.owner_id == owner_id))
    )
    row = result.first()
    if not row:
        return {"error": "Inbox item not found or access denied"}

    node, inbox = row

    if inbox.status != InboxItemStatus.PENDING:
        return {"error": "Inbox item is not pending"}

    job = await create_pipeline_job(
        db, owner_id, PipelineJobType.CLASSIFY_INBOX,
        target_node_id=node_id,
        idempotency_key=f"classify_inbox:{node_id}",
        prompt_version=PROMPT_VERSION,
    )
    await start_job(db, job.id)

    try:
        if is_llm_available():
            provider = get_llm_provider()
            prompt = CLASSIFY_INBOX_PROMPT_TEMPLATE.format(raw_text=inbox.raw_text)
            response = await provider.complete_json(prompt, system_prompt=CLASSIFY_INBOX_SYSTEM_PROMPT)
            model_version = provider.get_model_version()
            classification = response if isinstance(response, dict) else {"classification": "keep_inbox", "title": node.title, "confidence": 0.0}
        else:
            # Simple heuristic classification
            text = inbox.raw_text.lower()
            if any(word in text for word in ["todo", "do", "buy", "fix", "call", "schedule", "finish"]):
                classification = {"classification": "task", "title": node.title, "priority": "medium", "confidence": 0.4}
            elif any(word in text for word in ["decided", "learned", "realized", "insight", "lesson"]):
                classification = {"classification": "memory", "title": node.title, "memory_type": "insight", "confidence": 0.3}
            elif any(word in text for word in ["http", "www", "article", "read"]):
                classification = {"classification": "source_item", "title": node.title, "confidence": 0.3}
            else:
                classification = {"classification": "keep_inbox", "title": node.title, "confidence": 0.2}
            model_version = "heuristic"

        classification["model_version"] = model_version
        await complete_job(db, job.id, classification)
        return classification

    except Exception as e:
        logger.exception(f"Failed to classify inbox item {node_id}")
        await fail_job(db, job.id, str(e))
        return {"error": str(e)}
