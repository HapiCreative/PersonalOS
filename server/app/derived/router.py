"""
Derived layer router (Section 8.3 — Derived Layer).

Endpoints for signal scores, progress intelligence, retrieval modes,
and the context layer.

Layer: Derived (non-canonical, recomputable)
Invariants: U-03, U-04, D-02, D-03
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.derived.signal_score import (
    compute_signal_score,
    compute_signal_scores_batch,
    get_signal_score,
    get_signal_scores_for_nodes,
)
from server.app.derived.progress_intelligence import (
    compute_progress_intelligence,
    compute_progress_batch,
    get_progress_intelligence,
)
from server.app.derived.retrieval_modes import (
    retrieve,
    get_available_modes,
)
from server.app.derived.context_layer import (
    assemble_context_layer,
    ContextItem,
)
from server.app.derived.stale_detection import check_node_stale
from server.app.derived.schemas import DerivedExplanation

router = APIRouter(prefix="/api/derived", tags=["derived"])


# =============================================================================
# Signal Score schemas
# =============================================================================

class SignalScoreResponse(BaseModel):
    """
    Signal score response.
    Invariant D-03: Non-canonical, recomputable (D-02).
    """
    node_id: str
    score: float
    recency_score: float
    link_density_score: float
    completion_state_score: float
    reference_frequency_score: float
    user_interaction_score: float
    computed_at: str
    version: str | None = None


class SignalScoreBatchResponse(BaseModel):
    items: list[SignalScoreResponse]
    total: int


# =============================================================================
# Progress Intelligence schemas
# =============================================================================

class ProgressIntelligenceResponse(BaseModel):
    """
    Progress intelligence response.
    Invariant D-03: Non-canonical, recomputable (D-02).
    """
    node_id: str
    progress: float
    momentum: float
    consistency_streak: int
    drift_score: float
    last_progress_at: str | None = None
    computed_at: str
    version: str | None = None


class ProgressBatchResponse(BaseModel):
    items: list[ProgressIntelligenceResponse]
    total: int


# =============================================================================
# Retrieval Mode schemas
# =============================================================================

class RetrievalResultResponse(BaseModel):
    node_id: str
    node_type: str
    title: str
    summary: str | None = None
    signal_score: float | None = None
    mode_weight: float
    combined_score: float
    metadata: dict = Field(default_factory=dict)


class RetrievalResponse(BaseModel):
    mode: str
    items: list[RetrievalResultResponse]
    total: int


class RetrievalModeInfo(BaseModel):
    name: str
    description: str
    max_results: int
    type_weights: dict[str, float]
    recency_bias: float


# =============================================================================
# Context Layer schemas
# =============================================================================

class ContextItemResponse(BaseModel):
    """
    A single item in the context layer.
    Invariant U-03: Part of capped context layer (max 8 items).
    """
    category: str
    node_id: str
    node_type: str
    title: str
    relation_type: str | None = None
    edge_id: str | None = None
    weight: float | None = None
    confidence: float | None = None
    is_suggested: bool = False
    label: str | None = None
    signal_score: float | None = None
    metadata: dict = Field(default_factory=dict)


class ContextCategoryResponse(BaseModel):
    name: str
    items: list[ContextItemResponse]


class ContextLayerResponse(BaseModel):
    """
    Context layer response.
    Invariant U-03: Hard cap of 8 items.
    Invariant U-04: Per-category caps enforced.
    """
    items: list[ContextItemResponse]
    total_count: int
    categories: list[ContextCategoryResponse]
    node_id: str
    suppression_applied: bool = False


# =============================================================================
# Helper converters
# =============================================================================

def _signal_to_response(s) -> SignalScoreResponse:
    return SignalScoreResponse(
        node_id=str(s.node_id),
        score=s.score,
        recency_score=s.recency_score,
        link_density_score=s.link_density_score,
        completion_state_score=s.completion_state_score,
        reference_frequency_score=s.reference_frequency_score,
        user_interaction_score=s.user_interaction_score,
        computed_at=s.computed_at.isoformat() if s.computed_at else "",
        version=s.version,
    )


def _progress_to_response(p) -> ProgressIntelligenceResponse:
    return ProgressIntelligenceResponse(
        node_id=str(p.node_id),
        progress=p.progress,
        momentum=p.momentum,
        consistency_streak=p.consistency_streak,
        drift_score=p.drift_score,
        last_progress_at=p.last_progress_at.isoformat() if p.last_progress_at else None,
        computed_at=p.computed_at.isoformat() if p.computed_at else "",
        version=p.version,
    )


def _context_item_to_response(item: ContextItem) -> ContextItemResponse:
    return ContextItemResponse(
        category=item.category,
        node_id=str(item.node_id),
        node_type=item.node_type,
        title=item.title,
        relation_type=item.relation_type,
        edge_id=item.edge_id,
        weight=item.weight,
        confidence=item.confidence,
        is_suggested=item.is_suggested,
        label=item.label,
        signal_score=item.signal_score,
        metadata=item.metadata,
    )


# =============================================================================
# Signal Score endpoints
# =============================================================================

@router.get("/signal-score/{node_id}", response_model=SignalScoreResponse)
async def get_node_signal_score(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the cached signal score for a node.
    Invariant D-02: Score is recomputable.
    Invariant D-03: Score is non-canonical.
    """
    score = await get_signal_score(db, node_id)
    if score is None:
        raise HTTPException(status_code=404, detail="Signal score not found. Trigger computation first.")
    return _signal_to_response(score)


@router.post("/signal-score/{node_id}/compute", response_model=SignalScoreResponse)
async def compute_node_signal_score(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute (or recompute) the signal score for a node.
    Invariant D-02: Recomputable from Core + Temporal data.
    """
    score = await compute_signal_score(db, user.id, node_id)
    if score is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return _signal_to_response(score)


@router.post("/signal-score/compute-batch", response_model=SignalScoreBatchResponse)
async def compute_batch_signal_scores(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
):
    """
    Batch compute signal scores for all non-archived nodes.
    Invariant D-02: All results are recomputable.
    """
    scores = await compute_signal_scores_batch(db, user.id, limit=limit)
    return SignalScoreBatchResponse(
        items=[_signal_to_response(s) for s in scores],
        total=len(scores),
    )


# =============================================================================
# Progress Intelligence endpoints
# =============================================================================

@router.get("/progress/{node_id}", response_model=ProgressIntelligenceResponse)
async def get_node_progress(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get cached progress intelligence for a node (goal or task).
    Invariant D-02: Progress is recomputable.
    Invariant D-03: Progress is non-canonical.
    """
    pi = await get_progress_intelligence(db, node_id)
    if pi is None:
        raise HTTPException(status_code=404, detail="Progress intelligence not found. Trigger computation first.")
    return _progress_to_response(pi)


@router.post("/progress/{node_id}/compute", response_model=ProgressIntelligenceResponse)
async def compute_node_progress(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute (or recompute) progress intelligence for a node.
    Invariant D-02: Recomputable from task_execution_events + edges.
    """
    pi = await compute_progress_intelligence(db, user.id, node_id)
    if pi is None:
        raise HTTPException(status_code=404, detail="Node not found or not a goal/task")
    return _progress_to_response(pi)


@router.post("/progress/compute-batch", response_model=ProgressBatchResponse)
async def compute_batch_progress(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    node_type: str | None = Query(default=None, description="Filter by node type: goal or task"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    Batch compute progress intelligence for goals and tasks.
    Invariant D-02: All results are recomputable.
    """
    from server.app.core.models.enums import NodeType
    nt = None
    if node_type:
        try:
            nt = NodeType(node_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid node_type: {node_type}")

    results = await compute_progress_batch(db, user.id, node_type=nt, limit=limit)
    return ProgressBatchResponse(
        items=[_progress_to_response(p) for p in results],
        total=len(results),
    )


# =============================================================================
# Retrieval Mode endpoints
# =============================================================================

@router.get("/retrieval-modes", response_model=list[RetrievalModeInfo])
async def list_retrieval_modes():
    """List all available retrieval modes with their configuration."""
    modes = get_available_modes()
    return [RetrievalModeInfo(**m) for m in modes]


@router.get("/retrieve/{mode}", response_model=RetrievalResponse)
async def retrieve_by_mode(
    mode: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    q: str | None = Query(default=None, description="Optional query string"),
    limit: int = Query(default=None, ge=1, le=50),
):
    """
    Execute a retrieval mode to get ranked results.
    Available modes: factual_qa, execution_qa, daily_briefing, reflection, improvement, link_suggestion
    Invariant D-02: Results are recomputable.
    """
    try:
        results = await retrieve(db, user.id, mode, query=q, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RetrievalResponse(
        mode=mode,
        items=[
            RetrievalResultResponse(
                node_id=str(r.node_id),
                node_type=r.node_type,
                title=r.title,
                summary=r.summary,
                signal_score=r.signal_score,
                mode_weight=r.mode_weight,
                combined_score=r.combined_score,
                metadata=r.metadata,
            )
            for r in results
        ],
        total=len(results),
    )


# =============================================================================
# Context Layer endpoints
# =============================================================================

# =============================================================================
# Stale Detection endpoints (Phase 6)
# =============================================================================

class StaleCheckResponse(BaseModel):
    """
    Stale detection result for a single node.
    Invariant D-01: Includes DerivedExplanation.
    """
    is_stale: bool
    node_id: str
    stale_category: str | None = None
    days_stale: int | None = None
    prompt: str | None = None
    explanation: dict | None = None  # DerivedExplanation as dict


@router.get("/stale/{node_id}", response_model=StaleCheckResponse)
async def check_stale(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Check if a specific node is stale.
    Layer: Derived (computed from Core data).
    Invariant D-01: Result includes DerivedExplanation when stale.
    Invariant D-02: Fully recomputable.
    """
    item = await check_node_stale(db, user.id, node_id)
    if item is None:
        return StaleCheckResponse(is_stale=False, node_id=str(node_id))
    return StaleCheckResponse(
        is_stale=True,
        node_id=str(node_id),
        stale_category=item.stale_category,
        days_stale=item.days_stale,
        prompt=item.prompt,
        explanation=item.explanation.to_dict(),
    )


# =============================================================================
# Context Layer endpoints
# =============================================================================

@router.get("/context/{node_id}", response_model=ContextLayerResponse)
async def get_context_layer(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the context layer for a node.
    2-stage retrieval: explicit links (Stage 1) + suggested via embedding (Stage 2).

    Invariant U-03: Hard cap of 8 items.
    Invariant U-04: Per-category caps enforced.
    """
    result = await assemble_context_layer(db, user.id, node_id)

    # Build category responses
    category_order = [
        "backlinks", "outgoing_links", "provenance",
        "review_status", "ai_suggestions", "resurfaced", "decay_flags",
    ]
    categories = []
    for cat_name in category_order:
        cat_items = result.categories.get(cat_name, [])
        if cat_items:
            categories.append(ContextCategoryResponse(
                name=cat_name,
                items=[_context_item_to_response(item) for item in cat_items],
            ))

    return ContextLayerResponse(
        items=[_context_item_to_response(item) for item in result.items],
        total_count=result.total_count,
        categories=categories,
        node_id=str(result.node_id),
        suppression_applied=result.suppression_applied,
    )
