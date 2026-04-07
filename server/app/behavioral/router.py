"""
Behavioral layer router (Section 8.3).
Endpoints: GET /api/today
Layer: Behavioral (read-only assembly from Core + Derived data)
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.behavioral.today import assemble_today_view, TodayItem

import uuid
from datetime import date

router = APIRouter(prefix="/api/today", tags=["today"])


class TodayItemResponse(BaseModel):
    section: str
    item_type: str
    node_id: str | None = None
    title: str
    subtitle: str = ""
    priority: str | None = None
    due_date: date | None = None
    progress: float | None = None
    is_unsolicited: bool = False
    metadata: dict = Field(default_factory=dict)


class TodaySectionResponse(BaseModel):
    name: str
    items: list[TodayItemResponse]


class TodayViewResponse(BaseModel):
    """
    Today View behavioral surface response.
    Invariant U-02: total_count <= 10.
    Invariant U-04: per-section caps enforced.
    """
    items: list[TodayItemResponse]
    total_count: int
    sections: list[TodaySectionResponse]
    stage: str
    date: date


def _item_to_response(item: TodayItem) -> TodayItemResponse:
    return TodayItemResponse(
        section=item.section,
        item_type=item.item_type,
        node_id=str(item.node_id) if item.node_id else None,
        title=item.title,
        subtitle=item.subtitle,
        priority=item.priority,
        due_date=item.due_date,
        progress=item.progress,
        is_unsolicited=item.is_unsolicited,
        metadata=item.metadata,
    )


@router.get("", response_model=TodayViewResponse)
async def get_today_view(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the Today View behavioral surface.

    Invariant U-01: Max 2 unsolicited intelligence items.
    Invariant U-02: Hard cap of 10 items.
    Invariant U-04: Per-section caps enforced.
    Invariant U-05: Suppression precedence applied.
    """
    result = await assemble_today_view(db, user.id)

    items = [_item_to_response(item) for item in result.items]

    section_order = ["focus", "due", "habits", "learning", "goal_nudges", "review", "resurfaced", "journal"]
    sections = []
    for section_name in section_order:
        section_items = result.sections.get(section_name, [])
        if section_items:
            sections.append(TodaySectionResponse(
                name=section_name,
                items=[_item_to_response(item) for item in section_items],
            ))

    return TodayViewResponse(
        items=items,
        total_count=result.total_count,
        sections=sections,
        stage=result.stage,
        date=result.date,
    )
