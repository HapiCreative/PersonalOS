"""
LLM / AI Modes router (Section 8.3 — Behavioral Layer).
Single AI mode endpoint with mode parameter + background AI job endpoints.

API endpoints:
- POST /api/llm/query          (mode in body: ask|plan|reflect|improve)
- POST /api/llm/suggest-links/{node_id}
- POST /api/llm/enrich-source/{node_id}
- POST /api/llm/lint-kb/{node_id}
- POST /api/llm/classify-inbox/{node_id}
- POST /api/llm/briefing
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import AIMode
from server.app.behavioral.ai_modes import execute_mode, generate_briefing
from server.app.behavioral.link_suggestions import suggest_links_for_node
from server.app.behavioral.background_ai import (
    enrich_source, lint_kb_entry, classify_inbox_item,
)

router = APIRouter(prefix="/api/llm", tags=["llm"])


# =============================================================================
# Request/Response schemas
# =============================================================================

class AIQueryRequest(BaseModel):
    mode: AIMode
    query: str = Field(..., min_length=1, max_length=5000)


class CitationResponse(BaseModel):
    node_id: str
    title: str
    node_type: str


class ContextItemResponse(BaseModel):
    node_id: str
    node_type: str
    title: str
    summary: str | None = None
    combined_score: float


class AIModeResponse(BaseModel):
    mode: str
    query: str
    response_text: str
    response_data: dict
    citations: list[CitationResponse] = []
    context_items: list[ContextItemResponse] = []
    duration_ms: int
    model_version: str
    prompt_version: str


class LinkSuggestionResponse(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    relation_type: str
    confidence: float | None
    rationale: str


class SuggestLinksResponse(BaseModel):
    node_id: str
    suggestions: list[LinkSuggestionResponse]
    total: int


class EnrichSourceResponse(BaseModel):
    node_id: str
    status: str
    enrichments: dict = {}
    error: str | None = None


class LintKBResponse(BaseModel):
    node_id: str
    quality_score: float | None = None
    is_stale: bool | None = None
    issues: list[str] = []
    suggestions: list[str] = []
    error: str | None = None


class ClassifyInboxResponse(BaseModel):
    node_id: str
    classification: str | None = None
    title: str | None = None
    priority: str | None = None
    memory_type: str | None = None
    confidence: float | None = None
    rationale: str | None = None
    error: str | None = None


class BriefingResponse(BaseModel):
    bullets: list[str]


# =============================================================================
# Single AI Mode endpoint (Section 5.5)
# =============================================================================

def _build_response(result) -> AIModeResponse:
    """Build AIModeResponse from an AIModeResult."""
    return AIModeResponse(
        mode=result.mode,
        query=result.query,
        response_text=result.response_text,
        response_data=result.response_data,
        citations=[CitationResponse(**c) for c in result.citations],
        context_items=[
            ContextItemResponse(
                node_id=str(item.node_id),
                node_type=item.node_type,
                title=item.title,
                summary=item.summary,
                combined_score=item.combined_score,
            )
            for item in result.context.items
        ],
        duration_ms=result.duration_ms,
        model_version=result.model_version,
        prompt_version=result.prompt_version,
    )


@router.post("/query", response_model=AIModeResponse, status_code=200)
async def query_ai(
    request: AIQueryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Single AI mode endpoint. Pass mode (ask|plan|reflect|improve) in the body.
    Section 5.5: Dispatches to the appropriate retrieval + LLM pipeline.
    """
    result = await execute_mode(db, user.id, request.mode, request.query)
    return _build_response(result)


# =============================================================================
# Link suggestions (Section 5.5)
# =============================================================================

@router.post("/suggest-links/{node_id}", response_model=SuggestLinksResponse, status_code=200)
async def suggest_links(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate link suggestions for a node.
    Creates edges with origin=llm, state=pending_review.
    """
    edges = await suggest_links_for_node(db, user.id, node_id)
    suggestions = [
        LinkSuggestionResponse(
            edge_id=str(edge.id),
            source_id=str(edge.source_id),
            target_id=str(edge.target_id),
            relation_type=edge.relation_type.value,
            confidence=edge.confidence,
            rationale=edge.metadata_.get("suggestion_rationale", "") if edge.metadata_ else "",
        )
        for edge in edges
    ]
    return SuggestLinksResponse(
        node_id=str(node_id),
        suggestions=suggestions,
        total=len(suggestions),
    )


# =============================================================================
# Background AI jobs (Section 5.4, 5.5)
# =============================================================================

@router.post("/enrich-source/{node_id}", response_model=EnrichSourceResponse, status_code=200)
async def enrich_source_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Source auto-enrichment via node_enrichments. Section 5.4 Stage 3."""
    result = await enrich_source(db, user.id, node_id)
    error = result.get("error")
    if error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error)
    return EnrichSourceResponse(
        node_id=str(node_id),
        status=result.get("status", "unknown"),
        enrichments=result.get("enrichments", {}),
    )


@router.post("/lint-kb/{node_id}", response_model=LintKBResponse, status_code=200)
async def lint_kb_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """KB lint pipeline. Section 5.5: Detect stale entries."""
    result = await lint_kb_entry(db, user.id, node_id)
    error = result.get("error")
    if error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error)
    return LintKBResponse(
        node_id=str(node_id),
        quality_score=result.get("quality_score"),
        is_stale=result.get("is_stale"),
        issues=result.get("issues", []),
        suggestions=result.get("suggestions", []),
    )


@router.post("/classify-inbox/{node_id}", response_model=ClassifyInboxResponse, status_code=200)
async def classify_inbox_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Inbox auto-classification. Section 5.4: Async behavioral job."""
    result = await classify_inbox_item(db, user.id, node_id)
    error = result.get("error")
    if error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error)
    return ClassifyInboxResponse(
        node_id=str(node_id),
        classification=result.get("classification"),
        title=result.get("title"),
        priority=result.get("priority"),
        memory_type=result.get("memory_type"),
        confidence=result.get("confidence"),
        rationale=result.get("rationale"),
    )


# =============================================================================
# AI Briefing (Section 5.1)
# =============================================================================

@router.post("/briefing", response_model=BriefingResponse, status_code=200)
async def briefing_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate AI briefing for Today View (3-5 bullets). Section 5.1."""
    bullets = await generate_briefing(db, user.id)
    return BriefingResponse(bullets=bullets)
