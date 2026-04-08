"""Sources domain services — re-exports all public functions."""

from server.app.domains.sources.services.fragments import (
    create_fragment,
    list_fragments,
)
from server.app.domains.sources.services.promotion import promote_source
from server.app.domains.sources.services.sources import (
    check_duplicate_by_embedding,
    create_source,
    get_source,
    list_sources,
    update_source,
)

__all__ = [
    "check_duplicate_by_embedding",
    "create_fragment",
    "create_source",
    "get_source",
    "list_fragments",
    "list_sources",
    "promote_source",
    "update_source",
]
