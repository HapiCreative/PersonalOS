"""Inbox schemas sub-package. Re-exports all schema classes."""

from server.app.domains.inbox.schemas.inbox_items import (
    InboxItemCreate,
    InboxItemListResponse,
    InboxItemResponse,
    InboxItemUpdate,
)

__all__ = [
    "InboxItemCreate",
    "InboxItemListResponse",
    "InboxItemResponse",
    "InboxItemUpdate",
]
