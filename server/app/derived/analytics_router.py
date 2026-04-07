"""
Analytics API router (Section 4.7, 8.3 — Derived Layer).

Analytics dashboard endpoints organized by three layers:
1. Execution Dashboard (primary): task completion, planning accuracy, focus time, streaks
2. Strategic Alignment (secondary): goal progress, drift trends, plan vs actual
3. Wellbeing Patterns (tertiary): mood over time, mood-productivity correlations

Two-tier analytics model:
- Tier A (operational): today/7d/14d — live query
- Tier B (trend): 30d/90d/6mo/1y — pre-aggregated rollups

Invariant D-02: All data is recomputable.
Invariant D-03: Non-canonical storage.
Invariant D-04: Analytics output classification (descriptive/correlational/recommendation).
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.derived.analytics_rollups import (
    AnalyticsClassification,
    AnalyticsOutput,
    TierAMetrics,
    compute_tier_a_metrics,
    compute_daily_rollup,
    compute_weekly_rollup,
    compute_rollups_for_range,
    get_daily_rollups,
    get_weekly_rollups,
    compute_planning_accuracy_insight,
    compute_mood_productivity_correlation,
    generate_completion_recommendation,
)
from server.app.derived.semantic_clustering import (
    compute_semantic_clusters,
    get_clusters,
    get_node_cluster,
    get_cluster_peers,
    ClusterInfo,
)
from server.app.derived.smart_resurfacing import (
    resurface_for_context,
    resurface_for_today,
    ResurfacedItem,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# =============================================================================
# Response schemas
# =============================================================================


class DerivedFactorResponse(BaseModel):
    signal: str
    value: object
    weight: float


class DerivedExplanationResponse(BaseModel):
    """Invariant D-01: DerivedExplanation for user-facing Derived outputs."""
    summary: str
    factors: list[DerivedFactorResponse]
    confidence: float | None = None
    generated_at: str | None = None
    version: str | None = None


class AnalyticsOutputResponse(BaseModel):
    """
    Invariant D-04: Every analytics output classified as
    descriptive / correlational / recommendation.
    """
    classification: str  # "descriptive" | "correlational" | "recommendation"
    label: str  # "" for descriptive, "Pattern detected" for correlational, "Suggestion" for recommendation
    explanation: DerivedExplanationResponse
    data: dict = Field(default_factory=dict)


class TierAResponse(BaseModel):
    """Tier A operational metrics (live query)."""
    period: str
    start_date: str
    end_date: str
    tasks_completed: int
    tasks_planned: int
    tasks_planned_completed: int
    planning_accuracy: float
    focus_seconds_total: int
    focus_sessions_count: int
    journal_entries: int
    avg_mood: float | None
    current_streak: int


class DailyRollupResponse(BaseModel):
    """Single daily rollup record."""
    date: str
    tasks_completed: int
    tasks_planned: int
    tasks_planned_completed: int
    planning_accuracy: float
    focus_seconds_total: int
    focus_seconds_by_goal: dict
    journal_mood_score: float | None
    active_goal_progress_delta: float
    streak_eligible_flag: bool
    computed_at: str


class WeeklyRollupResponse(BaseModel):
    """Single weekly rollup record."""
    week_start_date: str
    completion_rate: float
    planning_accuracy: float
    total_focus_time: int
    goal_time_distribution: dict
    momentum: float
    drift_summary: list
    avg_mood: float | None
    mood_productivity_correlation_inputs: list
    computed_at: str


class TierBResponse(BaseModel):
    """Tier B trend metrics (pre-aggregated rollups)."""
    period: str
    start_date: str
    end_date: str
    daily_rollups: list[DailyRollupResponse]
    weekly_rollups: list[WeeklyRollupResponse]


class ExecutionDashboardResponse(BaseModel):
    """
    Execution Dashboard (primary view).
    Invariant D-04: All outputs classified.
    """
    tier_a: TierAResponse
    insights: list[AnalyticsOutputResponse]


class StrategicAlignmentResponse(BaseModel):
    """
    Strategic Alignment (secondary tab).
    Invariant D-04: All outputs classified.
    """
    tier_b: TierBResponse
    insights: list[AnalyticsOutputResponse]


class WellbeingPatternsResponse(BaseModel):
    """
    Wellbeing Patterns (tertiary overlay).
    Invariant D-04: All outputs classified.
    """
    mood_data: list[dict]  # [{date, mood_score}]
    insights: list[AnalyticsOutputResponse]


class ClusterMemberResponse(BaseModel):
    node_id: str
    title: str
    type: str
    similarity: float


class ClusterResponse(BaseModel):
    cluster_id: str | None
    label: str
    node_count: int
    coherence_score: float
    members: list[ClusterMemberResponse]


class ClustersListResponse(BaseModel):
    clusters: list[ClusterResponse]
    total: int


class ResurfacedItemResponse(BaseModel):
    node_id: str
    node_type: str
    title: str
    reason: str
    signal_score: float | None
    similarity: float | None
    cluster_label: str | None
    explanation: DerivedExplanationResponse | None
    metadata: dict = Field(default_factory=dict)


class ResurfacingResponse(BaseModel):
    items: list[ResurfacedItemResponse]
    total: int
    mode: str  # "context" or "today"


class RollupComputeResponse(BaseModel):
    daily_count: int
    weekly_count: int
    start_date: str
    end_date: str


# =============================================================================
# Converters
# =============================================================================


def _analytics_output_to_response(output: AnalyticsOutput) -> AnalyticsOutputResponse:
    exp = output.explanation
    return AnalyticsOutputResponse(
        classification=output.classification,
        label=output.label,
        explanation=DerivedExplanationResponse(
            summary=exp.summary,
            factors=[
                DerivedFactorResponse(signal=f.signal, value=f.value, weight=f.weight)
                for f in exp.factors
            ],
            confidence=exp.confidence,
            generated_at=exp.generated_at.isoformat() if exp.generated_at else None,
            version=exp.version,
        ),
        data=output.data,
    )


def _tier_a_to_response(metrics: TierAMetrics) -> TierAResponse:
    return TierAResponse(
        period=metrics.period,
        start_date=metrics.start_date.isoformat(),
        end_date=metrics.end_date.isoformat(),
        tasks_completed=metrics.tasks_completed,
        tasks_planned=metrics.tasks_planned,
        tasks_planned_completed=metrics.tasks_planned_completed,
        planning_accuracy=round(metrics.planning_accuracy, 3),
        focus_seconds_total=metrics.focus_seconds_total,
        focus_sessions_count=metrics.focus_sessions_count,
        journal_entries=metrics.journal_entries,
        avg_mood=round(metrics.avg_mood, 2) if metrics.avg_mood else None,
        current_streak=metrics.current_streak,
    )


def _daily_rollup_to_response(r) -> DailyRollupResponse:
    return DailyRollupResponse(
        date=r.date.isoformat(),
        tasks_completed=r.tasks_completed,
        tasks_planned=r.tasks_planned,
        tasks_planned_completed=r.tasks_planned_completed,
        planning_accuracy=round(r.planning_accuracy, 3),
        focus_seconds_total=r.focus_seconds_total,
        focus_seconds_by_goal=r.focus_seconds_by_goal or {},
        journal_mood_score=r.journal_mood_score,
        active_goal_progress_delta=r.active_goal_progress_delta,
        streak_eligible_flag=r.streak_eligible_flag,
        computed_at=r.computed_at.isoformat() if r.computed_at else "",
    )


def _weekly_rollup_to_response(r) -> WeeklyRollupResponse:
    return WeeklyRollupResponse(
        week_start_date=r.week_start_date.isoformat(),
        completion_rate=round(r.completion_rate, 3),
        planning_accuracy=round(r.planning_accuracy, 3),
        total_focus_time=r.total_focus_time,
        goal_time_distribution=r.goal_time_distribution or {},
        momentum=round(r.momentum, 2),
        drift_summary=r.drift_summary or [],
        avg_mood=round(r.avg_mood, 2) if r.avg_mood else None,
        mood_productivity_correlation_inputs=r.mood_productivity_correlation_inputs or [],
        computed_at=r.computed_at.isoformat() if r.computed_at else "",
    )


def _cluster_to_response(cluster: ClusterInfo) -> ClusterResponse:
    members = [
        ClusterMemberResponse(
            node_id=str(nid),
            title=t,
            type=nt,
            similarity=round(s, 3),
        )
        for nid, t, nt, s in zip(
            cluster.node_ids, cluster.node_titles, cluster.node_types, cluster.similarities
        )
    ]
    return ClusterResponse(
        cluster_id=str(cluster.cluster_id) if cluster.cluster_id else None,
        label=cluster.label,
        node_count=cluster.node_count,
        coherence_score=round(cluster.coherence_score, 3),
        members=members,
    )


def _resurfaced_to_response(item: ResurfacedItem) -> ResurfacedItemResponse:
    exp_resp = None
    if item.explanation:
        exp_resp = DerivedExplanationResponse(
            summary=item.explanation.summary,
            factors=[
                DerivedFactorResponse(signal=f.signal, value=f.value, weight=f.weight)
                for f in item.explanation.factors
            ],
            confidence=item.explanation.confidence,
            generated_at=item.explanation.generated_at.isoformat() if item.explanation.generated_at else None,
            version=item.explanation.version,
        )
    return ResurfacedItemResponse(
        node_id=str(item.node_id),
        node_type=item.node_type,
        title=item.title,
        reason=item.reason,
        signal_score=round(item.signal_score, 3) if item.signal_score else None,
        similarity=round(item.similarity, 3) if item.similarity else None,
        cluster_label=item.cluster_label,
        explanation=exp_resp,
        metadata=item.metadata,
    )


# =============================================================================
# Execution Dashboard endpoints (primary)
# =============================================================================


@router.get("/execution", response_model=ExecutionDashboardResponse)
async def get_execution_dashboard(
    period: str = Query(default="7d", description="Time period: today, 7d, 14d"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Execution Dashboard (primary view).
    Task completion rates, planning accuracy, focus time, streaks.

    Tier A: Live query for today/7d/14d.
    Invariant D-04: All outputs explicitly classified.
    """
    if period not in ("today", "7d", "14d"):
        raise HTTPException(status_code=400, detail="period must be today, 7d, or 14d")

    metrics = await compute_tier_a_metrics(db, user.id, period)
    tier_a = _tier_a_to_response(metrics)

    # Generate insights (Invariant D-04: each is classified)
    insights: list[AnalyticsOutputResponse] = []

    # Descriptive: task completion summary
    insights.append(_analytics_output_to_response(AnalyticsOutput(
        classification="descriptive",
        label="",
        explanation=_make_completion_explanation(metrics),
        data={
            "tasks_completed": metrics.tasks_completed,
            "tasks_planned": metrics.tasks_planned,
            "planning_accuracy": round(metrics.planning_accuracy, 3),
            "current_streak": metrics.current_streak,
        },
    )))

    return ExecutionDashboardResponse(tier_a=tier_a, insights=insights)


@router.get("/strategic", response_model=StrategicAlignmentResponse)
async def get_strategic_alignment(
    period: str = Query(default="30d", description="Time period: 30d, 90d, 6mo, 1y"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Strategic Alignment (secondary tab).
    Goal progress over time, drift score trends, plan vs actual.

    Tier B: Pre-aggregated rollups for 30d+.
    Invariant D-04: All outputs explicitly classified.
    """
    today = date.today()
    if period == "30d":
        start = today - timedelta(days=30)
    elif period == "90d":
        start = today - timedelta(days=90)
    elif period == "6mo":
        start = today - timedelta(days=180)
    elif period == "1y":
        start = today - timedelta(days=365)
    else:
        raise HTTPException(status_code=400, detail="period must be 30d, 90d, 6mo, or 1y")

    daily_rollups = await get_daily_rollups(db, user.id, start, today)
    weekly_rollups = await get_weekly_rollups(db, user.id, start, today)

    tier_b = TierBResponse(
        period=period,
        start_date=start.isoformat(),
        end_date=today.isoformat(),
        daily_rollups=[_daily_rollup_to_response(d) for d in daily_rollups],
        weekly_rollups=[_weekly_rollup_to_response(w) for w in weekly_rollups],
    )

    # Generate insights (Invariant D-04)
    insights: list[AnalyticsOutputResponse] = []

    # Descriptive: planning accuracy
    planning_insight = compute_planning_accuracy_insight(daily_rollups)
    if planning_insight:
        insights.append(_analytics_output_to_response(planning_insight))

    # Recommendation: completion pattern
    completion_rec = generate_completion_recommendation(daily_rollups)
    if completion_rec:
        insights.append(_analytics_output_to_response(completion_rec))

    return StrategicAlignmentResponse(tier_b=tier_b, insights=insights)


@router.get("/wellbeing", response_model=WellbeingPatternsResponse)
async def get_wellbeing_patterns(
    period: str = Query(default="30d", description="Time period: 30d, 90d, 6mo, 1y"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Wellbeing Patterns (tertiary overlay).
    Mood over time, mood vs productivity correlations.

    Invariant D-04: All outputs explicitly classified.
    The system must never say "X causes Y" — only "X correlates with Y."
    """
    today = date.today()
    if period == "30d":
        start = today - timedelta(days=30)
    elif period == "90d":
        start = today - timedelta(days=90)
    elif period == "6mo":
        start = today - timedelta(days=180)
    elif period == "1y":
        start = today - timedelta(days=365)
    else:
        raise HTTPException(status_code=400, detail="period must be 30d, 90d, 6mo, or 1y")

    daily_rollups = await get_daily_rollups(db, user.id, start, today)
    weekly_rollups = await get_weekly_rollups(db, user.id, start, today)

    # Mood data
    mood_data = [
        {"date": d.date.isoformat(), "mood_score": d.journal_mood_score}
        for d in daily_rollups
        if d.journal_mood_score is not None
    ]

    # Generate insights (Invariant D-04)
    insights: list[AnalyticsOutputResponse] = []

    # Correlational: mood-productivity correlation
    # Invariant D-04: "Pattern detected", never implies causation
    correlation_insight = compute_mood_productivity_correlation(weekly_rollups)
    if correlation_insight:
        insights.append(_analytics_output_to_response(correlation_insight))

    return WellbeingPatternsResponse(
        mood_data=mood_data,
        insights=insights,
    )


# =============================================================================
# Rollup computation endpoints
# =============================================================================


@router.post("/rollups/compute", response_model=RollupComputeResponse)
async def compute_rollups(
    days: int = Query(default=7, ge=1, le=365, description="Number of days to compute"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute (or recompute) daily + weekly rollups for the last N days.
    Invariant D-02: Fully recomputable — safe to rerun.
    """
    today = date.today()
    start = today - timedelta(days=days - 1)

    dailies, weeklies = await compute_rollups_for_range(db, user.id, start, today)

    return RollupComputeResponse(
        daily_count=len(dailies),
        weekly_count=len(weeklies),
        start_date=start.isoformat(),
        end_date=today.isoformat(),
    )


@router.post("/rollups/compute-today", response_model=DailyRollupResponse)
async def compute_today_rollup(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute the daily rollup for today."""
    rollup = await compute_daily_rollup(db, user.id, date.today())
    return _daily_rollup_to_response(rollup)


# =============================================================================
# Semantic Clustering endpoints (Section 4.9)
# =============================================================================


@router.get("/clusters", response_model=ClustersListResponse)
async def list_clusters(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get existing semantic clusters.
    Invariant D-02: Clusters are recomputable from embeddings.
    Invariant D-03: Non-canonical.
    """
    clusters = await get_clusters(db, user.id)
    return ClustersListResponse(
        clusters=[_cluster_to_response(c) for c in clusters],
        total=len(clusters),
    )


@router.post("/clusters/compute", response_model=ClustersListResponse)
async def recompute_clusters(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Recompute semantic clusters from all node embeddings.
    Invariant D-02: Full recomputation — replaces existing clusters.
    """
    clusters = await compute_semantic_clusters(db, user.id)
    return ClustersListResponse(
        clusters=[_cluster_to_response(c) for c in clusters],
        total=len(clusters),
    )


@router.get("/clusters/node/{node_id}", response_model=ClusterResponse | None)
async def get_node_cluster_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the semantic cluster a node belongs to."""
    cluster = await get_node_cluster(db, node_id)
    if cluster is None:
        return None
    return _cluster_to_response(cluster)


@router.get("/clusters/node/{node_id}/peers")
async def get_cluster_peers_endpoint(
    node_id: uuid.UUID,
    limit: int = Query(default=5, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get related nodes from the same cluster as the given node."""
    peers = await get_cluster_peers(db, node_id, limit=limit)
    return {"node_id": str(node_id), "peers": peers, "total": len(peers)}


# =============================================================================
# Smart Resurfacing endpoints (Section 4.10)
# =============================================================================


@router.get("/resurface/context/{node_id}", response_model=ResurfacingResponse)
async def resurface_context_layer(
    node_id: uuid.UUID,
    limit: int = Query(default=5, ge=1, le=10),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Context layer resurfacing (pull-based).
    3-5 items, triggered on node open.

    Section 4.10: Context layer — pull-based, 3-5 items.
    Invariant D-02: Recomputable from embeddings + clusters.
    """
    items = await resurface_for_context(db, user.id, node_id, limit=limit)
    return ResurfacingResponse(
        items=[_resurfaced_to_response(i) for i in items],
        total=len(items),
        mode="context",
    )


@router.get("/resurface/today", response_model=ResurfacingResponse)
async def resurface_today_mode(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Today Mode resurfacing (push-based).
    1-2 items max, computed at daily load.

    Section 4.10: Today Mode — push-based, 1-2 items max.
    Invariant U-01: Max 2 unsolicited intelligence items.
    """
    items = await resurface_for_today(db, user.id)
    return ResurfacingResponse(
        items=[_resurfaced_to_response(i) for i in items],
        total=len(items),
        mode="today",
    )


# =============================================================================
# Helpers
# =============================================================================


def _make_completion_explanation(metrics: TierAMetrics):
    """Create a DerivedExplanation for task completion summary."""
    from server.app.derived.schemas import DerivedExplanation, DerivedFactor
    return DerivedExplanation(
        summary=(
            f"Completed {metrics.tasks_completed} tasks in {metrics.period}. "
            f"Current streak: {metrics.current_streak} days."
        ),
        factors=[
            DerivedFactor(signal="tasks_completed", value=metrics.tasks_completed, weight=0.4),
            DerivedFactor(signal="tasks_planned", value=metrics.tasks_planned, weight=0.2),
            DerivedFactor(signal="planning_accuracy", value=round(metrics.planning_accuracy, 3), weight=0.2),
            DerivedFactor(signal="current_streak", value=metrics.current_streak, weight=0.2),
        ],
        generated_at=datetime.now(timezone.utc),
        version="v1",
    )
