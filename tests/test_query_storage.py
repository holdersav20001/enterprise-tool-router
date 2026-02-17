"""Integration tests for query_history storage module.

Week 4 Commit 27: Query History Storage

These tests require Postgres to be running:
    docker-compose up postgres

Run integration tests only:
    pytest -m integration tests/test_query_storage.py
"""
import pytest
import time
from datetime import datetime, timedelta
from enterprise_tool_router.query_storage import (
    store_query,
    lookup_query,
    get_query_by_hash,
    cleanup_expired_queries,
    _hash_query
)


@pytest.mark.integration
class TestQueryStorage:
    """Test query storage and retrieval."""

    def test_store_and_retrieve_query(self):
        """Test storing and retrieving a query."""
        import time
        query_text = f"show revenue by region for test {time.time()}"

        store_query(
            natural_language_query=query_text,
            generated_sql="SELECT region, SUM(revenue) FROM sales_fact GROUP BY region LIMIT 100",
            confidence=0.95,
            result_size_bytes=2048,
            row_count=5,
            execution_time_ms=150,
            tokens_input=100,
            tokens_output=50,
            cost_usd=0.001
        )

        # Retrieve
        result = lookup_query(query_text)
        assert result is not None
        assert result["generated_sql"] == "SELECT region, SUM(revenue) FROM sales_fact GROUP BY region LIMIT 100"
        assert result["confidence"] == 0.95
        assert result["use_count"] == 1
        assert result["row_count"] == 5
        assert result["execution_time_ms"] == 150
        assert result["tokens_input"] == 100
        assert result["tokens_output"] == 50
        assert result["cost_usd"] == 0.001

    def test_duplicate_query_increments_use_count(self):
        """Test that storing same query increments use_count."""
        query = "test query for deduplication " + str(time.time())

        # First store
        store_query(query, "SELECT 1", 0.9, 100, 1, 50)
        result1 = lookup_query(query)
        assert result1["use_count"] == 1

        # Second store (duplicate) - should increment use_count
        time.sleep(0.1)  # Small delay to ensure different timestamp
        store_query(query, "SELECT 1", 0.9, 100, 1, 50)
        result2 = lookup_query(query)
        assert result2["use_count"] == 2

        # Verify last_used_at was updated
        assert result2["last_used_at"] >= result1["last_used_at"]

    def test_expired_queries_not_returned(self):
        """Test that expired queries are not retrieved."""
        query = "expired query " + str(time.time())

        # Store with 0-day retention (immediate expiration)
        store_query(
            query,
            "SELECT 1",
            0.9,
            100,
            1,
            50,
            retention_days=0
        )

        # Should not be found
        result = lookup_query(query)
        assert result is None

    def test_cleanup_expired_queries(self):
        """Test that cleanup removes expired queries."""
        query = "old query " + str(time.time())

        # Store expired query
        store_query(query, "SELECT 1", 0.9, 100, 1, 50, retention_days=0)

        # Verify it exists but expired (won't be returned by lookup)
        assert lookup_query(query) is None

        # Run cleanup
        deleted_count = cleanup_expired_queries()
        assert deleted_count >= 1

    def test_query_hash_normalization(self):
        """Test that query hashing normalizes case and whitespace."""
        # These should all hash to the same value
        hash1 = _hash_query("  Show Revenue  ")
        hash2 = _hash_query("show revenue")
        hash3 = _hash_query("SHOW REVENUE")

        assert hash1 == hash2 == hash3

    def test_get_query_by_hash(self):
        """Test retrieving query by hash directly."""
        query = "test hash lookup " + str(time.time())
        store_query(query, "SELECT 2", 0.8, 200, 2, 100)

        # Get hash and retrieve
        query_hash = _hash_query(query)
        result = get_query_by_hash(query_hash)

        assert result is not None
        assert result["natural_language_query"] == query
        assert result["generated_sql"] == "SELECT 2"

    def test_store_with_optional_fields(self):
        """Test storing query with optional fields."""
        query = "test optional fields " + str(time.time())

        store_query(
            natural_language_query=query,
            generated_sql="SELECT 3",
            confidence=0.7,
            result_size_bytes=300,
            row_count=3,
            execution_time_ms=200,
            tokens_input=50,
            tokens_output=25,
            cost_usd=0.0005,
            user_id="test_user",
            correlation_id="test-correlation-123"
        )

        result = lookup_query(query)
        assert result is not None
        assert result["user_id"] == "test_user"
        assert result["correlation_id"] == "test-correlation-123"

    def test_custom_retention_period(self):
        """Test storing with custom retention period."""
        query = "test custom retention " + str(time.time())

        # Store with 60-day retention
        store_query(
            query,
            "SELECT 4",
            0.9,
            100,
            1,
            50,
            retention_days=60
        )

        result = lookup_query(query)
        assert result is not None
        # Should still be retrievable (not expired)
        assert result["generated_sql"] == "SELECT 4"


@pytest.mark.integration
class TestQueryStorageEdgeCases:
    """Test edge cases and error handling."""

    def test_nonexistent_query_returns_none(self):
        """Test that looking up nonexistent query returns None."""
        result = lookup_query("this query definitely does not exist " + str(time.time()))
        assert result is None

    def test_nonexistent_hash_returns_none(self):
        """Test that looking up nonexistent hash returns None."""
        fake_hash = "0" * 64  # Valid SHA256 length but doesn't exist
        result = get_query_by_hash(fake_hash)
        assert result is None

    def test_large_query_storage(self):
        """Test storing query with large SQL statement."""
        query = "large query test " + str(time.time())
        large_sql = "SELECT * FROM sales_fact WHERE " + " AND ".join([f"col{i} = 1" for i in range(100)])

        store_query(query, large_sql, 0.9, 10000, 100, 500)

        result = lookup_query(query)
        assert result is not None
        assert result["generated_sql"] == large_sql

    def test_special_characters_in_query(self):
        """Test storing query with special characters."""
        query = "query with 'quotes' and \"double quotes\" and $symbols$ " + str(time.time())

        store_query(query, "SELECT 5", 0.9, 100, 1, 50)

        result = lookup_query(query)
        assert result is not None
        assert result["natural_language_query"] == query
