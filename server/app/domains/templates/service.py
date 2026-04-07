"""
Template domain service (Section 2.4, 8.1).
Handles template CRUD operations.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.template import Template
from server.app.core.models.enums import TemplateTargetType


async def create_template(
    db: AsyncSession,
    owner_id: uuid.UUID,
    name: str,
    target_type: TemplateTargetType,
    structure: dict | None = None,
    is_system: bool = False,
) -> Template:
    """Create a template."""
    template = Template(
        owner_id=owner_id,
        name=name,
        target_type=target_type,
        structure=structure or {},
        is_system=is_system,
    )
    db.add(template)
    await db.flush()
    return template


async def get_template(
    db: AsyncSession,
    owner_id: uuid.UUID,
    template_id: uuid.UUID,
) -> Template | None:
    """Get a template by ID, enforcing ownership."""
    stmt = select(Template).where(
        Template.id == template_id,
        Template.owner_id == owner_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_templates(
    db: AsyncSession,
    owner_id: uuid.UUID,
    target_type: TemplateTargetType | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Template], int]:
    """List templates with optional type filter, enforcing ownership."""
    base_filter = [Template.owner_id == owner_id]
    if target_type:
        base_filter.append(Template.target_type == target_type)

    count_stmt = select(func.count()).select_from(Template).where(*base_filter)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Template)
        .where(*base_filter)
        .order_by(Template.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    templates = list(result.scalars().all())

    return templates, total


async def update_template(
    db: AsyncSession,
    owner_id: uuid.UUID,
    template_id: uuid.UUID,
    name: str | None = None,
    structure: dict | None = None,
) -> Template | None:
    """Update template fields, enforcing ownership."""
    template = await get_template(db, owner_id, template_id)
    if template is None:
        return None

    if name is not None:
        template.name = name
    if structure is not None:
        template.structure = structure

    await db.flush()
    return template


async def delete_template(
    db: AsyncSession,
    owner_id: uuid.UUID,
    template_id: uuid.UUID,
) -> bool:
    """Delete a template, enforcing ownership."""
    template = await get_template(db, owner_id, template_id)
    if template is None:
        return False

    await db.delete(template)
    await db.flush()
    return True
