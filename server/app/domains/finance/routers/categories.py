"""Category endpoints for the finance domain."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.schemas.categories import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryTreeResponse,
    CategoryUpdate,
)
from server.app.domains.finance.services.categories import (
    create_category,
    delete_category,
    get_category,
    list_categories,
    list_categories_tree,
    seed_categories_for_user,
    update_category,
)

router = APIRouter()


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category_endpoint(
    body: CategoryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a user financial category."""
    try:
        cat = await create_category(
            db, user.id,
            name=body.name,
            parent_id=body.parent_id,
            icon=body.icon,
            sort_order=body.sort_order,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return CategoryResponse.model_validate(cat)


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories_endpoint(
    parent_id: uuid.UUID | None = Query(default=..., description="Filter by parent (null for top-level)"),
    limit: int = Query(default=100, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List categories with optional parent filter."""
    items, total = await list_categories(db, user.id, parent_id=parent_id, limit=limit, offset=offset)
    return CategoryListResponse(
        items=[CategoryResponse.model_validate(c) for c in items],
        total=total,
    )


@router.get("/categories/tree", response_model=list[CategoryTreeResponse])
async def list_categories_tree_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all categories as a hierarchical tree."""
    all_cats = await list_categories_tree(db, user.id)

    # Build tree from flat list
    cat_map: dict[uuid.UUID, CategoryTreeResponse] = {}
    roots: list[CategoryTreeResponse] = []

    for c in all_cats:
        tree_item = CategoryTreeResponse(
            id=c.id,
            user_id=c.user_id,
            name=c.name,
            parent_id=c.parent_id,
            icon=c.icon,
            is_system=c.is_system,
            sort_order=c.sort_order,
            created_at=c.created_at,
            children=[],
        )
        cat_map[c.id] = tree_item

    for c in all_cats:
        tree_item = cat_map[c.id]
        if c.parent_id and c.parent_id in cat_map:
            cat_map[c.parent_id].children.append(tree_item)
        else:
            roots.append(tree_item)

    return roots


@router.get("/categories/{category_id}", response_model=CategoryResponse)
async def get_category_endpoint(
    category_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single category."""
    cat = await get_category(db, user.id, category_id)
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return CategoryResponse.model_validate(cat)


@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category_endpoint(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a category."""
    try:
        cat = await update_category(
            db, user.id, category_id,
            name=body.name,
            parent_id=body.parent_id if body.parent_id is not None else ...,
            icon=body.icon if body.icon is not None else ...,
            sort_order=body.sort_order,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return CategoryResponse.model_validate(cat)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_endpoint(
    category_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a category.
    Invariant F-12: Blocked if transactions reference it.
    """
    try:
        success = await delete_category(db, user.id, category_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")


@router.post("/categories/seed", response_model=list[CategoryResponse])
async def seed_categories_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Seed system default categories for the current user. Idempotent."""
    cats = await seed_categories_for_user(db, user.id)
    return [CategoryResponse.model_validate(c) for c in cats]
