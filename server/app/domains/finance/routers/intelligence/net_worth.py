"""Net worth endpoint (Section 4.1)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.routers.intelligence._helpers import (
    explanation_to_response,
)
from server.app.domains.finance.schemas.derived import NetWorthResponse
from server.app.domains.finance.services.net_worth import compute_net_worth

router = APIRouter()


@router.get("/net-worth", response_model=NetWorthResponse)
async def get_net_worth(
    as_of_date: date | None = Query(default=None),
    base_currency: str | None = Query(default=None, min_length=3, max_length=3),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Section 4.1: Net worth engine with liquid vs illiquid breakdown."""
    result = await compute_net_worth(db, user.id, as_of_date, base_currency)
    return NetWorthResponse(
        as_of_date=result["as_of_date"],
        base_currency=result["base_currency"],
        net_worth=result["net_worth"],
        liquid_net_worth=result["liquid_net_worth"],
        total_assets=result["total_assets"],
        total_liabilities=result["total_liabilities"],
        liquid_assets=result["liquid_assets"],
        illiquid_assets=result["illiquid_assets"],
        account_count=result["account_count"],
        breakdown=result["breakdown"],
        explanation=explanation_to_response(result["explanation"]),
    )
