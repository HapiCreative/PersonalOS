"""
Phase 10: Redis caching strategy and materialized view refresh.
Section 4.1: Signal scores cached in materialized view.
Invariant D-02: All cached values are recomputable.
Invariant D-03: Non-canonical storage for query convenience.
"""

import json
import logging
from datetime import timedelta
from typing import Any

import redis.asyncio as redis
from sqlalchemy import text

from server.app.config import settings

logger = logging.getLogger(__name__)

# Global Redis connection pool
_redis_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Get or create the Redis connection."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None


# =============================================================================
# Generic cache operations
# =============================================================================


async def cache_get(key: str) -> Any | None:
    """Get a value from the cache. Returns None on miss or error."""
    try:
        r = await get_redis()
        raw = await r.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.debug("Cache miss for key=%s (connection error)", key)
        return None


async def cache_set(key: str, value: Any, ttl: timedelta | None = None) -> None:
    """Set a value in the cache with optional TTL."""
    try:
        r = await get_redis()
        raw = json.dumps(value, default=str)
        if ttl:
            await r.setex(key, int(ttl.total_seconds()), raw)
        else:
            await r.set(key, raw)
    except Exception:
        logger.debug("Cache set failed for key=%s", key)


async def cache_delete(key: str) -> None:
    """Delete a key from the cache."""
    try:
        r = await get_redis()
        await r.delete(key)
    except Exception:
        logger.debug("Cache delete failed for key=%s", key)


async def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a pattern."""
    try:
        r = await get_redis()
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match=pattern, count=100)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        logger.debug("Cache delete pattern failed for pattern=%s", pattern)


# =============================================================================
# Domain-specific cache keys
# =============================================================================


def signal_score_key(node_id: str) -> str:
    """Cache key for a node's signal score."""
    return f"signal_score:{node_id}"


def context_layer_key(node_id: str) -> str:
    """Cache key for a node's context layer."""
    return f"context_layer:{node_id}"


def today_view_key(user_id: str) -> str:
    """Cache key for a user's today view."""
    return f"today_view:{user_id}"


def progress_key(node_id: str) -> str:
    """Cache key for a node's progress intelligence."""
    return f"progress:{node_id}"


# =============================================================================
# Cache invalidation helpers
# =============================================================================


async def invalidate_node_caches(node_id: str) -> None:
    """
    Invalidate all caches related to a node.
    Called when a node is updated, deleted, or edges change.
    """
    await cache_delete(signal_score_key(node_id))
    await cache_delete(context_layer_key(node_id))
    await cache_delete(progress_key(node_id))


async def invalidate_user_caches(user_id: str) -> None:
    """Invalidate all caches for a user (e.g., today view)."""
    await cache_delete(today_view_key(user_id))


# =============================================================================
# Materialized view refresh
# Section 4.1: Signal score materialized view refresh scheduling.
# Invariant D-02: Recomputable — refresh rebuilds from Core data.
# =============================================================================


async def refresh_materialized_views(db_session) -> dict:
    """
    Refresh all materialized views.
    Called on schedule or manually for cache warming.
    """
    results = {}

    try:
        await db_session.execute(
            text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_signal_scores")
        )
        results["mv_signal_scores"] = "refreshed"
        logger.info("Refreshed mv_signal_scores")
    except Exception:
        logger.exception("Failed to refresh mv_signal_scores")
        results["mv_signal_scores"] = "error"

    return results


# =============================================================================
# Cache TTL defaults (Phase 10: caching strategy)
# =============================================================================

# Signal scores: relatively stable, refresh every 15 minutes
SIGNAL_SCORE_TTL = timedelta(minutes=15)

# Context layer: invalidated on edge changes, moderate TTL
CONTEXT_LAYER_TTL = timedelta(minutes=10)

# Today view: short TTL since it's the primary surface
TODAY_VIEW_TTL = timedelta(minutes=5)

# Progress: moderate TTL, invalidated on task completion events
PROGRESS_TTL = timedelta(minutes=15)
