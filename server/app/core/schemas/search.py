"""
Search request/response schemas.
Phase 5: Adds signal_score to search results for ranking display.
"""

from pydantic import BaseModel, Field

from server.app.core.schemas.node import NodeResponse


class SearchResultItem(BaseModel):
    """
    A single search result with optional signal score.
    Phase 5: Signal score included when available for ranking display.
    """
    node: NodeResponse
    signal_score: float | None = None


class SearchResponse(BaseModel):
    items: list[NodeResponse]
    total: int
    query: str


class SearchWithScoresResponse(BaseModel):
    """Phase 5: Search response with signal scores for ranking."""
    items: list[SearchResultItem]
    total: int
    query: str
