"""
Templates domain router (Section 8.3).
Endpoints: POST/GET /api/templates
Layer: Core (system configuration)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import TemplateTargetType
from server.app.domains.templates.schemas import (
    TemplateCreate,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
)
from server.app.domains.templates.services import (
    create_template,
    delete_template,
    get_template,
    list_templates,
    update_template,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template_endpoint(
    body: TemplateCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new template."""
    template = await create_template(
        db, user.id, body.name, body.target_type, body.structure, body.is_system,
    )
    return TemplateResponse.model_validate(template)


@router.get("", response_model=TemplateListResponse)
async def list_templates_endpoint(
    target_type: TemplateTargetType | None = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List templates with optional type filter."""
    templates, total = await list_templates(db, user.id, target_type, limit, offset)
    return TemplateListResponse(
        items=[TemplateResponse.model_validate(t) for t in templates],
        total=total,
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template_endpoint(
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single template by ID."""
    template = await get_template(db, user.id, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return TemplateResponse.model_validate(template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template_endpoint(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update template fields."""
    template = await update_template(
        db, user.id, template_id, body.name, body.structure,
    )
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return TemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template_endpoint(
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a template."""
    success = await delete_template(db, user.id, template_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
