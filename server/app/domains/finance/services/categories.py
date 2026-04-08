"""Category service functions for the finance domain."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import FinancialCategory, FinancialTransaction


SYSTEM_DEFAULT_CATEGORIES = [
    ("Groceries", 1),
    ("Rent/Mortgage", 2),
    ("Utilities", 3),
    ("Dining", 4),
    ("Transportation", 5),
    ("Entertainment", 6),
    ("Healthcare", 7),
    ("Insurance", 8),
    ("Subscriptions", 9),
    ("Personal Care", 10),
    ("Education", 11),
    ("Gifts/Donations", 12),
    ("Income", 13),
    ("Investments", 14),
    ("Fees", 15),
    ("Other", 16),
]


async def seed_categories_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[FinancialCategory]:
    """
    Seed system default categories for a user.
    Section 2.5: System-seeded defaults created on user creation.
    Idempotent — skips duplicates via conflict detection.
    """
    categories = []
    for name, sort_order in SYSTEM_DEFAULT_CATEGORIES:
        # Check if already exists
        stmt = select(FinancialCategory).where(
            FinancialCategory.user_id == user_id,
            FinancialCategory.name == name,
            FinancialCategory.parent_id.is_(None),
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            categories.append(existing)
            continue

        cat = FinancialCategory(
            user_id=user_id,
            name=name,
            is_system=True,
            sort_order=sort_order,
        )
        db.add(cat)
        categories.append(cat)

    await db.flush()
    return categories


async def create_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    parent_id: uuid.UUID | None = None,
    icon: str | None = None,
    sort_order: int = 0,
) -> FinancialCategory:
    """Create a user financial category. User-created categories have is_system=false."""
    # Validate parent exists and belongs to user if specified
    if parent_id is not None:
        parent = await get_category(db, user_id, parent_id)
        if parent is None:
            raise ValueError(f"Parent category {parent_id} not found or not owned by user")

    cat = FinancialCategory(
        user_id=user_id,
        name=name,
        parent_id=parent_id,
        icon=icon,
        is_system=False,
        sort_order=sort_order,
    )
    db.add(cat)
    await db.flush()
    return cat


async def get_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
) -> FinancialCategory | None:
    """Get a category by ID, enforcing ownership."""
    stmt = select(FinancialCategory).where(
        FinancialCategory.id == category_id,
        FinancialCategory.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_categories(
    db: AsyncSession,
    user_id: uuid.UUID,
    parent_id: uuid.UUID | None = ...,  # type: ignore[assignment]
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[FinancialCategory], int]:
    """List categories with optional parent filter, enforcing ownership."""
    base_filter = [FinancialCategory.user_id == user_id]

    if parent_id is not ...:
        if parent_id is None:
            base_filter.append(FinancialCategory.parent_id.is_(None))
        else:
            base_filter.append(FinancialCategory.parent_id == parent_id)

    count_stmt = (
        select(func.count())
        .select_from(FinancialCategory)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(FinancialCategory)
        .where(*base_filter)
        .order_by(FinancialCategory.sort_order.asc(), FinancialCategory.name.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return items, total


async def list_categories_tree(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[FinancialCategory]:
    """List all categories for a user (for building hierarchy tree in app layer)."""
    stmt = (
        select(FinancialCategory)
        .where(FinancialCategory.user_id == user_id)
        .order_by(FinancialCategory.sort_order.asc(), FinancialCategory.name.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
    name: str | None = None,
    parent_id: uuid.UUID | None = ...,  # type: ignore[assignment]
    icon: str | None = ...,  # type: ignore[assignment]
    sort_order: int | None = None,
) -> FinancialCategory | None:
    """Update a category, enforcing ownership."""
    cat = await get_category(db, user_id, category_id)
    if cat is None:
        return None

    if name is not None:
        cat.name = name
    if parent_id is not ...:
        # Validate parent if setting one
        if parent_id is not None:
            parent = await get_category(db, user_id, parent_id)
            if parent is None:
                raise ValueError(f"Parent category {parent_id} not found or not owned by user")
            # Prevent self-referencing
            if parent_id == category_id:
                raise ValueError("Category cannot be its own parent")
        cat.parent_id = parent_id
    if icon is not ...:
        cat.icon = icon
    if sort_order is not None:
        cat.sort_order = sort_order

    await db.flush()
    return cat


async def delete_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
) -> bool:
    """
    Delete a category. Invariant F-12: blocked if transactions reference it.
    DB enforces via RESTRICT FK, but we check at app layer first for a clear error.
    """
    cat = await get_category(db, user_id, category_id)
    if cat is None:
        return False

    # Invariant F-12: Check if any transactions reference this category
    tx_count_stmt = (
        select(func.count())
        .select_from(FinancialTransaction)
        .where(FinancialTransaction.category_id == category_id)
    )
    tx_count = (await db.execute(tx_count_stmt)).scalar_one()
    if tx_count > 0:
        raise ValueError(
            f"Invariant F-12: Cannot delete category '{cat.name}' — "
            f"{tx_count} transaction(s) reference it"
        )

    # Also check subcategory references
    sub_count_stmt = (
        select(func.count())
        .select_from(FinancialTransaction)
        .where(FinancialTransaction.subcategory_id == category_id)
    )
    sub_count = (await db.execute(sub_count_stmt)).scalar_one()
    if sub_count > 0:
        raise ValueError(
            f"Invariant F-12: Cannot delete category '{cat.name}' — "
            f"{sub_count} transaction(s) reference it as subcategory"
        )

    await db.delete(cat)
    await db.flush()
    return True
