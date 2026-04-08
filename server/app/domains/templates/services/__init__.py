"""Template services sub-package — re-exports all public functions."""

from server.app.domains.templates.services.template import (
    create_template,
    delete_template,
    get_template,
    list_templates,
    update_template,
)

__all__ = [
    "create_template",
    "delete_template",
    "get_template",
    "list_templates",
    "update_template",
]
