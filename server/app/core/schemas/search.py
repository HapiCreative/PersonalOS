"""Search request/response schemas."""

from pydantic import BaseModel, Field

from server.app.core.schemas.node import NodeResponse


class SearchResponse(BaseModel):
    items: list[NodeResponse]
    total: int
    query: str
