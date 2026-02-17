"""Pytest fixtures and configuration.

Provides shared fixtures for both unit and integration tests.
"""
import sys
from pathlib import Path
import pytest
import os
from typing import Generator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# Integration test fixtures for Redis
@pytest.fixture(scope="session")
def redis_url() -> str:
    """Get Redis URL from environment or use default."""
    # Use 127.0.0.1 instead of localhost for Windows/Docker compatibility
    return os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")


@pytest.fixture(scope="function")
def redis_cache(redis_url: str) -> Generator:
    """Create a CacheManager connected to real Redis for integration tests.

    This fixture:
    1. Creates a real Redis connection
    2. Clears the test database before each test
    3. Yields the cache manager
    4. Cleans up after the test

    Requires Redis to be running (docker-compose up redis).
    Mark tests with @pytest.mark.integration to use this fixture.
    """
    from enterprise_tool_router.cache import CacheManager

    # Create cache with real Redis connection
    cache = CacheManager(ttl_seconds=60, redis_url=redis_url, enabled=True)

    # Skip test if Redis is not available
    if not cache.is_enabled:
        pytest.skip("Redis not available - start with 'docker-compose up redis'")

    # Clear Redis before test (important for test isolation)
    cache.clear()
    cache.reset_stats()

    yield cache

    # Cleanup after test
    cache.clear()


@pytest.fixture(scope="function")
def redis_client(redis_url: str) -> Generator:
    """Get raw Redis client for integration tests.

    Useful for tests that need direct Redis access.
    """
    try:
        import redis
        # Use explicit connection for better Windows/Docker compatibility
        client = redis.Redis(
            host='127.0.0.1',
            port=6379,
            db=0,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        client.ping()

        # Clear before test
        client.flushdb()

        yield client

        # Cleanup
        client.flushdb()
        client.close()

    except Exception as e:
        pytest.skip(f"Redis not available - start with 'docker-compose up redis': {e}")


# Week 4 Commit 27: Test isolation for query_history
@pytest.fixture(scope="function")
def clean_query_history():
    """Clear query_history table before test for isolation.

    Use this fixture in unit tests that need to ensure no cached queries
    from previous runs interfere with test behavior.

    Example:
        def test_cache_miss(clean_query_history):
            # Test starts with empty query_history
            result = planner.plan("unique query")
    """
    try:
        from enterprise_tool_router.db import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM query_history")
            conn.commit()
    except Exception:
        # Table doesn't exist or DB not available - that's fine
        pass

    yield

    # Optionally clean up after test too
    try:
        from enterprise_tool_router.db import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM query_history")
            conn.commit()
    except Exception:
        pass
