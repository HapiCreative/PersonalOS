"""
Today View behavioral service (Section 5.1).
Assembles the primary behavioral surface: the Today View.

4-stage daily cycle: commit -> execute -> reflect -> learn

Today Mode ranking policy:
- Hard cap: 10 items (Invariant U-02)
- Per-section caps (Invariant U-04)
- Max 2 unsolicited intelligence items (Invariant U-01)
- Suppression rules (Invariant U-05)

Invariants enforced:
- U-01: Max 2 unsolicited intelligence items
- U-02: Today Mode volume cap (10 items)
- U-04: Per-section caps required
- U-05: Suppression precedence
- D-03: Progress is non-canonical (for goal nudges)
"""

import uuid
from datetime import date, datetime, timezone
from dataclasses import dataclass, field

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, TaskNode, GoalNode, JournalNode
from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    NodeType, TaskStatus, TaskPriority, GoalStatus,
    EdgeRelationType, EdgeState,
)
from server.app.derived.stale_detection import detect_all_stale
from server.app.temporal.snooze_records import get_snoozed_node_ids
from server.app.temporal.daily_plans_service import get_daily_plan
from server.app.temporal.focus_sessions_service import get_active_focus_session


# =============================================================================
# Invariant U-04: Per-section caps
# Section: (min, max) items
# =============================================================================
SECTION_CAPS = {
    "focus": (1, 3),
    "due": (0, 3),
    "habits": (0, 2),
    "learning": (0, 3),
    "goal_nudges": (0, 1),
    "review": (0, 1),
    "resurfaced": (0, 1),
    "journal": (0, 1),
}

# Invariant U-02: Hard cap on total items
TODAY_HARD_CAP = 10

# Invariant U-01: Max unsolicited intelligence items
MAX_UNSOLICITED = 2


@dataclass
class TodayItem:
    """A single item in the Today View."""
    section: str
    item_type: str  # 'task', 'goal_nudge', 'journal_prompt', etc.
    node_id: uuid.UUID | None = None
    title: str = ""
    subtitle: str = ""
    priority: str | None = None
    due_date: date | None = None
    progress: float | None = None
    is_unsolicited: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class TodayViewResult:
    """The assembled Today View."""
    items: list[TodayItem]
    total_count: int
    sections: dict[str, list[TodayItem]]
    stage: str  # current daily cycle stage
    date: date
    has_plan: bool = False  # Phase 7: whether a daily plan exists for today
    active_focus_task_id: uuid.UUID | None = None  # Phase 7: active focus session task


async def _get_due_overdue_tasks(
    db: AsyncSession,
    owner_id: uuid.UUID,
    today: date,
) -> list[TodayItem]:
    """Get due/overdue tasks (P1 priority in Today View)."""
    stmt = (
        select(Node, TaskNode)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.TASK,
            Node.archived_at.is_(None),
            TaskNode.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS]),
            TaskNode.due_date.isnot(None),
            TaskNode.due_date <= today,
        )
        .order_by(
            TaskNode.due_date.asc(),
            TaskNode.priority.desc(),
        )
        .limit(10)  # Fetch more, cap applied later
    )
    result = await db.execute(stmt)
    rows = list(result.all())

    items = []
    for node, task in rows:
        overdue = task.due_date < today if task.due_date else False
        items.append(TodayItem(
            section="due",
            item_type="task",
            node_id=node.id,
            title=node.title,
            subtitle=f"{'Overdue' if overdue else 'Due today'} - {task.priority.value}",
            priority=task.priority.value,
            due_date=task.due_date,
            metadata={"status": task.status.value, "overdue": overdue},
        ))
    return items


async def _get_goal_nudges(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> list[TodayItem]:
    """
    Get goal nudges (P4 priority in Today View).
    Show active goals with low progress or approaching end dates.
    Invariant D-03: progress is non-canonical.
    """
    stmt = (
        select(Node, GoalNode)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.GOAL,
            Node.archived_at.is_(None),
            GoalNode.status == GoalStatus.ACTIVE,
        )
        .order_by(GoalNode.progress.asc(), GoalNode.end_date.asc().nullslast())
        .limit(5)
    )
    result = await db.execute(stmt)
    rows = list(result.all())

    items = []
    for node, goal in rows:
        subtitle_parts = []
        if goal.progress < 0.5:
            subtitle_parts.append(f"{int(goal.progress * 100)}% complete")
        if goal.end_date:
            subtitle_parts.append(f"Due {goal.end_date.isoformat()}")
        if goal.timeframe_label:
            subtitle_parts.append(goal.timeframe_label)

        items.append(TodayItem(
            section="goal_nudges",
            item_type="goal_nudge",
            node_id=node.id,
            title=node.title,
            subtitle=" - ".join(subtitle_parts) if subtitle_parts else "Active goal",
            progress=goal.progress,
            is_unsolicited=True,  # Goal nudges are system-generated
            metadata={"status": goal.status.value},
        ))
    return items


async def _get_journal_prompt(
    db: AsyncSession,
    owner_id: uuid.UUID,
    today: date,
) -> list[TodayItem]:
    """Check if user has journaled today; if not, add a prompt."""
    stmt = (
        select(func.count())
        .select_from(Node)
        .join(JournalNode, JournalNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.JOURNAL_ENTRY,
            JournalNode.entry_date == today,
        )
    )
    count = (await db.execute(stmt)).scalar_one()

    if count == 0:
        return [TodayItem(
            section="journal",
            item_type="journal_prompt",
            title="Write today's journal entry",
            subtitle="Reflect on your day",
            is_unsolicited=True,
        )]
    return []


async def _get_cleanup_prompts(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> list[TodayItem]:
    """
    Get cleanup prompts for Today View (Phase 6).
    Shows a summary of stale items needing attention.
    Invariant U-05: Cleanup only if no active focus session (checked in suppression).
    """
    all_stale = await detect_all_stale(db, owner_id)
    # Filter out snoozed items (visibility precedence: archived > snoozed > stale)
    snoozed_ids = await get_snoozed_node_ids(db)
    visible_stale = [item for item in all_stale if item.node_id not in snoozed_ids]

    if not visible_stale:
        return []

    # Group by category for summary
    by_category: dict[str, int] = {}
    for item in visible_stale:
        by_category[item.stale_category] = by_category.get(item.stale_category, 0) + 1

    summary_parts = []
    for cat, count in sorted(by_category.items()):
        summary_parts.append(f"{count} {cat.replace('_', ' ')}")

    return [TodayItem(
        section="review",
        item_type="cleanup_prompt",
        title=f"{len(visible_stale)} items need cleanup",
        subtitle=", ".join(summary_parts[:3]),
        is_unsolicited=True,
        metadata={"total_stale": len(visible_stale), "categories": by_category},
    )]


async def _get_in_progress_tasks(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> list[TodayItem]:
    """Get in-progress tasks as focus items."""
    stmt = (
        select(Node, TaskNode)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.TASK,
            Node.archived_at.is_(None),
            TaskNode.status == TaskStatus.IN_PROGRESS,
        )
        .order_by(TaskNode.priority.desc(), Node.updated_at.desc())
        .limit(5)
    )
    result = await db.execute(stmt)
    rows = list(result.all())

    items = []
    for node, task in rows:
        items.append(TodayItem(
            section="focus",
            item_type="task",
            node_id=node.id,
            title=node.title,
            subtitle=f"In progress - {task.priority.value}",
            priority=task.priority.value,
            due_date=task.due_date,
            metadata={"status": task.status.value},
        ))
    return items


def _apply_ranking_and_caps(
    sections: dict[str, list[TodayItem]],
) -> tuple[list[TodayItem], dict[str, list[TodayItem]]]:
    """
    Apply Today Mode ranking policy with invariant enforcement.

    Invariant U-02: Hard cap of 10 items total.
    Invariant U-04: Per-section caps.
    Invariant U-01: Max 2 unsolicited intelligence items.
    Invariant U-05: Suppression rules.
    """
    # Step 1: Apply per-section caps (Invariant U-04)
    capped_sections: dict[str, list[TodayItem]] = {}
    for section_name, items in sections.items():
        cap = SECTION_CAPS.get(section_name, (0, 3))
        max_items = cap[1]
        capped_sections[section_name] = items[:max_items]

    # Step 2: Count urgent due items for suppression rules
    urgent_due_count = sum(
        1 for item in capped_sections.get("due", [])
        if item.priority in ("urgent", "high")
    )

    # Invariant U-05: Suppression rules
    visible_count = sum(len(items) for items in capped_sections.values()
                        if items)  # count before suppressions

    # Suppression: Goal nudges only if <= 2 urgent due items
    if urgent_due_count > 2:
        capped_sections["goal_nudges"] = []

    # Suppression: Journal prompt only if < 7 visible items
    if visible_count >= 7:
        capped_sections["journal"] = []

    # Suppression: Resurfaced only if < 8 visible items
    if visible_count >= 8:
        capped_sections["resurfaced"] = []

    # Step 3: Enforce U-01: Max 2 unsolicited intelligence items
    unsolicited_count = 0
    for section_name in capped_sections:
        filtered = []
        for item in capped_sections[section_name]:
            if item.is_unsolicited:
                if unsolicited_count >= MAX_UNSOLICITED:
                    continue  # Suppress this unsolicited item
                unsolicited_count += 1
            filtered.append(item)
        capped_sections[section_name] = filtered

    # Step 4: Assemble in priority order and enforce hard cap (Invariant U-02)
    section_order = ["focus", "due", "habits", "learning", "goal_nudges", "review", "resurfaced", "journal"]
    all_items: list[TodayItem] = []
    for section_name in section_order:
        all_items.extend(capped_sections.get(section_name, []))

    # Hard cap (Invariant U-02)
    all_items = all_items[:TODAY_HARD_CAP]

    # Rebuild sections from capped items
    final_sections: dict[str, list[TodayItem]] = {}
    for item in all_items:
        final_sections.setdefault(item.section, []).append(item)

    return all_items, final_sections


async def _get_resurfaced_decisions(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> list[TodayItem]:
    """
    Phase PB: Get resurfaced decisions for Today View.
    Section 5.7: Decision resurfacing — query at load time.
    """
    from server.app.behavioral.decision_resurfacing import get_decisions_for_resurfacing

    result = await get_decisions_for_resurfacing(db, owner_id, limit=3)

    items = []
    for decision in result.items:
        reason_labels = {
            "review_due": "Review scheduled",
            "no_outcome_7d": "7 days without outcome",
            "no_outcome_30d": "30 days without outcome",
            "no_outcome_90d": "90 days without outcome",
        }
        items.append(TodayItem(
            section="resurfaced",
            item_type="decision_resurfacing",
            node_id=decision.node_id,
            title=decision.title,
            subtitle=reason_labels.get(decision.resurfacing_reason, "Needs review"),
            is_unsolicited=True,
            metadata={
                "resurfacing_reason": decision.resurfacing_reason,
                "days_since_creation": decision.days_since_creation,
                "has_outcome_edges": decision.has_outcome_edges,
            },
        ))
    return items


async def _get_planned_focus_tasks(
    db: AsyncSession,
    owner_id: uuid.UUID,
    task_ids: list[uuid.UUID],
) -> list[TodayItem]:
    """
    Phase 7: Get focus items from daily plan's selected tasks.
    When a morning commitment exists, these replace the default in-progress focus items.
    """
    if not task_ids:
        return []

    stmt = (
        select(Node, TaskNode)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .where(
            Node.id.in_(task_ids),
            Node.owner_id == owner_id,
            Node.type == NodeType.TASK,
            Node.archived_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    rows = {n.id: (n, t) for n, t in result.all()}

    items = []
    for tid in task_ids:
        if tid in rows:
            node, task = rows[tid]
            items.append(TodayItem(
                section="focus",
                item_type="task",
                node_id=node.id,
                title=node.title,
                subtitle=f"Committed - {task.priority.value}",
                priority=task.priority.value,
                due_date=task.due_date,
                metadata={"status": task.status.value, "planned": True},
            ))
    return items


async def assemble_today_view(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> TodayViewResult:
    """
    Assemble the Today View behavioral surface.

    Phase 7: Integrates daily plan awareness and active focus session.

    Invariant U-02: Hard cap of 10 items.
    Invariant U-04: Per-section caps.
    Invariant U-01: Max 2 unsolicited.
    Invariant U-05: Suppression precedence.
    """
    today = date.today()

    # Phase 7: Check for daily plan — if plan exists, use planned tasks for focus
    daily_plan = await get_daily_plan(db, owner_id, today)
    has_plan = daily_plan is not None

    if has_plan and daily_plan.selected_task_ids:
        # Use committed tasks as focus items
        focus_items = await _get_planned_focus_tasks(
            db, owner_id, daily_plan.selected_task_ids,
        )
    else:
        # No plan yet — fall back to in-progress tasks
        focus_items = await _get_in_progress_tasks(db, owner_id)

    # Phase 7: Check for active focus session
    active_session = await get_active_focus_session(db, owner_id)
    active_focus_task_id = active_session.task_id if active_session else None

    due_items = await _get_due_overdue_tasks(db, owner_id, today)
    goal_nudges = await _get_goal_nudges(db, owner_id)
    journal_prompt = await _get_journal_prompt(db, owner_id, today)
    # Phase 6: Cleanup prompts (Section 5.6)
    cleanup_prompts = await _get_cleanup_prompts(db, owner_id)

    # Phase PB: Decision resurfacing items in Today View
    resurfaced_items = await _get_resurfaced_decisions(db, owner_id)

    # Build sections dict
    sections: dict[str, list[TodayItem]] = {
        "focus": focus_items,
        "due": due_items,
        "goal_nudges": goal_nudges,
        "review": cleanup_prompts,  # Phase 6: cleanup prompts in review section
        "resurfaced": resurfaced_items,  # Phase PB: decision resurfacing
        "journal": journal_prompt,
        # Future phases will add: habits, learning
    }

    # Apply ranking and caps
    all_items, final_sections = _apply_ranking_and_caps(sections)

    # Determine daily cycle stage
    # Phase 7: plan-aware stage detection
    now = datetime.now(timezone.utc)
    hour = now.hour
    if has_plan and daily_plan.closed_at is not None:
        stage = "learn"  # Plan closed = learning phase
    elif not has_plan and hour < 12:
        stage = "commit"  # No plan yet in morning = commit phase
    elif has_plan and active_focus_task_id:
        stage = "execute"  # Active focus session = execute phase
    elif has_plan and hour < 17:
        stage = "execute"  # Plan exists, afternoon = execute phase
    elif hour >= 17:
        stage = "reflect"  # Evening = reflect phase
    else:
        stage = "execute"  # Default to execute if plan exists

    return TodayViewResult(
        items=all_items,
        total_count=len(all_items),
        sections=final_sections,
        stage=stage,
        date=today,
        has_plan=has_plan,
        active_focus_task_id=active_focus_task_id,
    )
