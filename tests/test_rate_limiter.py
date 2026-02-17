"""Tests for rate limiting.

Week 4 Commit 24: Rate Limiting

This test suite validates that:
1. Rate limits are enforced correctly
2. Sliding window algorithm works
3. Exceeded limits return structured errors
4. Stats are tracked properly
5. Integration with ToolRouter works
"""
import pytest
import time
from enterprise_tool_router.rate_limiter import RateLimiter, RateLimitError, RateLimitStats
from enterprise_tool_router.router import ToolRouter


class TestRateLimiterBasics:
    """Test basic rate limiter functionality."""

    def test_rate_limiter_allows_under_limit(self):
        """Test that requests under limit are allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        # First 5 requests should be allowed
        for i in range(5):
            assert limiter.is_allowed(f"user{i}") is True
            assert limiter.record_request(f"user{i}") is True

    def test_rate_limiter_rejects_over_limit(self):
        """Test that requests over limit are rejected."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        user_id = "user1"

        # First 3 requests allowed
        for i in range(3):
            assert limiter.record_request(user_id) is True

        # 4th request should be rejected
        assert limiter.is_allowed(user_id) is False
        assert limiter.record_request(user_id) is False

    def test_check_limit_raises_exception(self):
        """Test that check_limit raises RateLimitError when exceeded."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        user_id = "user1"

        # Exceed limit
        limiter.record_request(user_id)
        limiter.record_request(user_id)

        # Should raise exception
        with pytest.raises(RateLimitError) as exc_info:
            limiter.check_limit(user_id)

        error = exc_info.value
        assert error.identifier == user_id
        assert error.limit == 2
        assert error.window == 60
        assert error.retry_after >= 0

    def test_sliding_window_expires_old_requests(self):
        """Test that old requests outside window are not counted."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)  # 1 second window
        user_id = "user1"

        # Make 2 requests
        limiter.record_request(user_id)
        limiter.record_request(user_id)

        # Should be at limit
        assert limiter.is_allowed(user_id) is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        assert limiter.is_allowed(user_id) is True
        assert limiter.record_request(user_id) is True

    def test_per_user_isolation(self):
        """Test that limits are per-user, not global."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # User1 makes 2 requests
        limiter.record_request("user1")
        limiter.record_request("user1")

        # User1 is at limit
        assert limiter.is_allowed("user1") is False

        # User2 should still be allowed
        assert limiter.is_allowed("user2") is True
        assert limiter.record_request("user2") is True


class TestRateLimiterStats:
    """Test rate limiter statistics."""

    def test_stats_tracking(self):
        """Test that statistics are tracked correctly."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # Initial stats
        stats = limiter.get_stats()
        assert stats.total_requests == 0
        assert stats.allowed_requests == 0
        assert stats.rejected_requests == 0

        # Make some requests
        limiter.record_request("user1")  # allowed
        limiter.record_request("user1")  # allowed
        limiter.record_request("user1")  # rejected (3rd)
        limiter.record_request("user2")  # allowed

        stats = limiter.get_stats()
        assert stats.total_requests == 4
        assert stats.allowed_requests == 3
        assert stats.rejected_requests == 1

    def test_rejection_rate(self):
        """Test rejection rate calculation."""
        stats = RateLimitStats(
            total_requests=10,
            allowed_requests=7,
            rejected_requests=3,
            unique_identifiers=5
        )

        assert stats.rejection_rate == pytest.approx(0.3)

    def test_stats_to_dict(self):
        """Test stats dictionary conversion."""
        stats = RateLimitStats(
            total_requests=100,
            allowed_requests=90,
            rejected_requests=10,
            unique_identifiers=15
        )

        stats_dict = stats.to_dict()
        assert stats_dict["total_requests"] == 100
        assert stats_dict["allowed_requests"] == 90
        assert stats_dict["rejected_requests"] == 10
        assert stats_dict["rejection_rate"] == 0.1


class TestRateLimiterIntegration:
    """Test rate limiter integration with ToolRouter."""

    def test_router_with_rate_limiter(self):
        """Test that router uses rate limiter."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        router = ToolRouter(rate_limiter=limiter)

        # First 2 requests should succeed
        result1 = router.handle("SELECT * FROM sales_fact", user_id="user1")
        assert result1.result.notes != "rate_limit_exceeded"

        result2 = router.handle("SELECT * FROM sales_fact", user_id="user1")
        assert result2.result.notes != "rate_limit_exceeded"

        # 3rd request should be rate limited
        result3 = router.handle("SELECT * FROM sales_fact", user_id="user1")
        assert result3.result.notes == "rate_limit_exceeded"
        assert "Rate limit exceeded" in result3.result.data["error"]

    def test_router_structured_error_response(self):
        """
        Acceptance Criteria: Returns structured error when rate limited.
        """
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        router = ToolRouter(rate_limiter=limiter)

        # Exceed limit
        router.handle("test", user_id="user1")
        result = router.handle("test", user_id="user1")

        # Should have structured error
        assert result.result.notes == "rate_limit_exceeded"
        error_data = result.result.data

        # Check all required fields
        assert "error" in error_data
        assert "message" in error_data
        assert "limit" in error_data
        assert "window_seconds" in error_data
        assert "retry_after_seconds" in error_data
        assert "identifier" in error_data

        assert error_data["limit"] == 1
        assert error_data["window_seconds"] == 60
        assert error_data["identifier"] == "user1"

    def test_router_without_user_id_no_rate_limiting(self):
        """Test that router doesn't rate limit if user_id not provided."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        router = ToolRouter(rate_limiter=limiter)

        # Multiple requests without user_id should all work
        for _ in range(5):
            result = router.handle("SELECT * FROM sales_fact")
            assert result.result.notes != "rate_limit_exceeded"

    def test_router_creates_default_limiter(self):
        """Test that router creates default rate limiter if not provided."""
        router = ToolRouter()

        # Should have a rate limiter
        assert router._rate_limiter is not None
        assert router._rate_limiter.max_requests == 100
        assert router._rate_limiter.window_seconds == 60


class TestLoadScenarios:
    """
    Acceptance Criteria: Load test triggers limit.
    """

    def test_load_scenario_triggers_limit(self):
        """Test that high load triggers rate limit."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        user_id = "load_test_user"

        # Simulate load - 20 requests
        allowed_count = 0
        rejected_count = 0

        for _ in range(20):
            if limiter.record_request(user_id):
                allowed_count += 1
            else:
                rejected_count += 1

        # Should allow exactly 10, reject 10
        assert allowed_count == 10
        assert rejected_count == 10

        stats = limiter.get_stats()
        assert stats.total_requests == 20
        assert stats.allowed_requests == 10
        assert stats.rejected_requests == 10

    def test_burst_traffic_handling(self):
        """Test handling of burst traffic."""
        limiter = RateLimiter(max_requests=5, window_seconds=2)
        user_id = "burst_user"

        # Burst of requests
        for _ in range(5):
            assert limiter.record_request(user_id) is True

        # Next request should be rejected
        assert limiter.record_request(user_id) is False

        # Wait for window to reset
        time.sleep(2.1)

        # Should be allowed again
        assert limiter.record_request(user_id) is True


class TestRateLimiterConfig:
    """Test rate limiter configuration."""

    def test_disabled_limiter_allows_all(self):
        """Test that disabled limiter allows all requests."""
        limiter = RateLimiter(max_requests=1, window_seconds=60, enabled=False)

        # Should allow unlimited requests
        for _ in range(100):
            assert limiter.is_allowed("user1") is True
            assert limiter.record_request("user1") is True

    def test_clear_specific_user(self):
        """Test clearing rate limit for specific user."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        # Hit limit
        limiter.record_request("user1")
        assert limiter.is_allowed("user1") is False

        # Clear user1
        limiter.clear("user1")

        # Should be allowed again
        assert limiter.is_allowed("user1") is True

    def test_clear_all_users(self):
        """Test clearing all rate limit data."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        # Hit limits for multiple users
        limiter.record_request("user1")
        limiter.record_request("user2")

        assert limiter.is_allowed("user1") is False
        assert limiter.is_allowed("user2") is False

        # Clear all
        limiter.clear()

        # All should be allowed again
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user2") is True
