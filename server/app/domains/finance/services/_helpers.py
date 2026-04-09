"""
Finance domain — shared internal helpers.

Used across finance derived and behavioral services. Not part of the public
service API.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.user import User


DEFAULT_BASE_CURRENCY = "USD"


async def get_user_base_currency(db: AsyncSession, user_id: uuid.UUID) -> str:
    """
    Read the user's base currency from their settings JSONB.

    Falls back to DEFAULT_BASE_CURRENCY. Users table has no first-class
    base_currency column — it lives under settings per v6 Section 2.1.
    """
    stmt = select(User.settings).where(User.id == user_id)
    settings = (await db.execute(stmt)).scalar_one_or_none() or {}
    base_currency = settings.get("base_currency") if isinstance(settings, dict) else None
    if not base_currency:
        return DEFAULT_BASE_CURRENCY
    return str(base_currency).upper()


def start_of_month(d: date) -> date:
    """Return the first day of d's month."""
    return d.replace(day=1)


def end_of_month(d: date) -> date:
    """Return the last day of d's month."""
    next_month = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return next_month - timedelta(days=1)


def start_of_week(d: date) -> date:
    """Return the Monday of d's week (week starts Monday)."""
    return d - timedelta(days=d.weekday())


def end_of_week(d: date) -> date:
    """Return the Sunday of d's week."""
    return start_of_week(d) + timedelta(days=6)


def add_months(d: date, months: int) -> date:
    """Add N months to a date, clamping to end-of-month."""
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    # Clamp day for short months
    last_day = end_of_month(date(year, month, 1)).day
    return date(year, month, min(d.day, last_day))


def day_range(start: date, end: date) -> list[date]:
    """Inclusive list of dates from start to end."""
    if end < start:
        return []
    days = (end - start).days + 1
    return [start + timedelta(days=i) for i in range(days)]


def utc_now() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def datetime_at_start_of_day(d: date) -> datetime:
    """Return midnight UTC for a given date."""
    return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)


def datetime_at_end_of_day(d: date) -> datetime:
    """Return end-of-day UTC for a given date."""
    return datetime.combine(d, datetime.max.time(), tzinfo=timezone.utc)
