"""Template schemas sub-package — re-exports all schema classes."""

from server.app.domains.templates.schemas.template import (
    TemplateCreate,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
)

__all__ = [
    "TemplateCreate",
    "TemplateListResponse",
    "TemplateResponse",
    "TemplateUpdate",
]
