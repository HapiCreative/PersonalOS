"""
Template model (Section 2.4 - System Configuration).
Templates for creating tasks, journal entries, and goals.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.db.database import Base
from server.app.core.models.enums import TemplateTargetType


class Template(Base):
    """Section 2.4: templates table (System Configuration)."""
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[TemplateTargetType] = mapped_column(nullable=False)
    structure: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_templates_owner", "owner_id"),
        Index("idx_templates_target_type", "target_type"),
    )
