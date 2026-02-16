"""Tests for audit logging functionality."""
import pytest
import hashlib
import json
import time

from enterprise_tool_router.audit import (
    hash_data,
    log_audit_record,
    audit_context,
    get_audit_records
)
from enterprise_tool_router.schemas_audit import AuditRecordSchema


class TestAuditHashing:
    """Test audit data hashing functions."""

    def test_hash_data_returns_sha256(self):
        """hash_data returns valid SHA256 hex string."""
        data = {"query": "SELECT * FROM sales_fact"}
        result = hash_data(data)

        # SHA256 hex string is 64 characters
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_data_deterministic(self):
        """Same data produces same hash."""
        data = {"query": "SELECT * FROM sales_fact", "user": "test"}

        hash1 = hash_data(data)
        hash2 = hash_data(data)

        assert hash1 == hash2

    def test_hash_data_different_order_same_hash(self):
        """Dictionary keys in different order produce same hash (sorted)."""
        data1 = {"a": 1, "b": 2, "c": 3}
        data2 = {"c": 3, "a": 1, "b": 2}

        assert hash_data(data1) == hash_data(data2)

    def test_hash_data_different_values_different_hash(self):
        """Different data produces different hashes."""
        data1 = {"query": "SELECT * FROM sales_fact"}
        data2 = {"query": "SELECT * FROM job_runs"}

        assert hash_data(data1) != hash_data(data2)

    def test_hash_data_handles_various_types(self):
        """hash_data handles different data types."""
        test_cases = [
            {"str": "value"},
            {"int": 123},
            {"float": 45.67},
            {"bool": True},
            {"list": [1, 2, 3]},
            {"nested": {"a": {"b": "c"}}}
        ]

        for data in test_cases:
            result = hash_data(data)
            assert len(result) == 64


class TestAuditLogging:
    """Test audit record logging to database."""

    def test_log_audit_record_inserts_record(self):
        """log_audit_record successfully inserts to database."""
        # Log a test record
        log_audit_record(
            correlation_id="test-trace-001",
            tool="sql",
            action="query",
            input_data={"query": "SELECT * FROM sales_fact"},
            output_data={"rows": 16, "status": "success"},
            success=True,
            duration_ms=50,
            user_id="test_user"
        )

        # Verify it was inserted
        records = get_audit_records(correlation_id="test-trace-001")
        assert len(records) >= 1

        # Check the most recent record
        record = records[0]
        assert record["correlation_id"] == "test-trace-001"
        assert record["tool"] == "sql"
        assert record["action"] == "query"
        assert record["success"] is True
        assert record["duration_ms"] == 50
        assert record["user_id"] == "test_user"

    def test_log_audit_record_stores_correct_hashes(self):
        """Audit record contains correct SHA256 hashes."""
        input_data = {"query": "SELECT id FROM sales_fact"}
        output_data = {"rows": [{"id": 1}, {"id": 2}]}

        # Calculate expected hashes
        expected_input_hash = hash_data(input_data)
        expected_output_hash = hash_data(output_data)

        # Log record
        log_audit_record(
            correlation_id="test-trace-002",
            tool="sql",
            action="query",
            input_data=input_data,
            output_data=output_data,
            success=True,
            duration_ms=100
        )

        # Verify hashes
        records = get_audit_records(correlation_id="test-trace-002")
        record = records[0]

        assert record["input_hash"] == expected_input_hash
        assert record["output_hash"] == expected_output_hash

    def test_log_audit_record_without_user_id(self):
        """Audit record can be logged without user_id."""
        log_audit_record(
            correlation_id="test-trace-003",
            tool="vector",
            action="search",
            input_data={"query": "test"},
            output_data={"results": []},
            success=True,
            duration_ms=75
        )

        records = get_audit_records(correlation_id="test-trace-003")
        assert len(records) >= 1
        assert records[0]["user_id"] is None

    def test_log_audit_record_failure_case(self):
        """Audit record correctly logs failures."""
        log_audit_record(
            correlation_id="test-trace-004",
            tool="sql",
            action="query",
            input_data={"query": "DROP TABLE sales_fact"},
            output_data={"error": "Only SELECT allowed"},
            success=False,
            duration_ms=5
        )

        records = get_audit_records(correlation_id="test-trace-004")
        record = records[0]

        assert record["success"] is False
        assert record["duration_ms"] == 5


class TestAuditContext:
    """Test audit context manager."""

    def test_audit_context_logs_successful_operation(self):
        """audit_context logs successful operations."""
        correlation_id = "test-ctx-001"
        input_data = {"query": "SELECT * FROM sales_fact LIMIT 5"}

        with audit_context(correlation_id, "sql", "query", input_data) as ctx:
            # Simulate operation
            time.sleep(0.001)  # Ensure measurable duration
            result = {"rows": 5, "status": "success"}
            ctx.set_output(result)

        # Verify audit record
        records = get_audit_records(correlation_id=correlation_id)
        assert len(records) >= 1

        record = records[0]
        assert record["correlation_id"] == correlation_id
        assert record["success"] is True
        assert record["duration_ms"] >= 0  # Duration is recorded (may be 0 for fast operations)

    def test_audit_context_measures_duration(self):
        """audit_context accurately measures duration."""
        correlation_id = "test-ctx-002"

        with audit_context(correlation_id, "sql", "query", {"q": "test"}) as ctx:
            time.sleep(0.05)  # Sleep 50ms
            ctx.set_output({"result": "done"})

        records = get_audit_records(correlation_id=correlation_id)
        record = records[0]

        # Duration should be at least 50ms
        assert record["duration_ms"] >= 45  # Allow for timing variance

    def test_audit_context_handles_exceptions(self):
        """audit_context logs even when operation fails."""
        correlation_id = "test-ctx-003"

        with pytest.raises(ValueError):
            with audit_context(correlation_id, "sql", "query", {"q": "test"}) as ctx:
                raise ValueError("Test error")

        # Should still have logged the audit record
        records = get_audit_records(correlation_id=correlation_id)
        record = records[0]

        assert record["success"] is False
        assert record["correlation_id"] == correlation_id

    def test_audit_context_with_user_id(self):
        """audit_context accepts user_id parameter."""
        correlation_id = "test-ctx-004"

        with audit_context(
            correlation_id,
            "vector",
            "search",
            {"query": "test"},
            user_id="john@example.com"
        ) as ctx:
            ctx.set_output({"results": []})

        records = get_audit_records(correlation_id=correlation_id)
        assert records[0]["user_id"] == "john@example.com"


class TestAuditRetrieval:
    """Test retrieving audit records."""

    def test_get_audit_records_without_filter(self):
        """get_audit_records returns recent records."""
        records = get_audit_records(limit=10)

        assert isinstance(records, list)
        assert len(records) <= 10

    def test_get_audit_records_by_correlation_id(self):
        """get_audit_records filters by correlation_id."""
        # Create a unique correlation ID
        correlation_id = "test-retrieve-001"

        log_audit_record(
            correlation_id=correlation_id,
            tool="sql",
            action="query",
            input_data={"q": "test1"},
            output_data={"r": "result1"},
            success=True,
            duration_ms=10
        )

        log_audit_record(
            correlation_id=correlation_id,
            tool="sql",
            action="query",
            input_data={"q": "test2"},
            output_data={"r": "result2"},
            success=True,
            duration_ms=15
        )

        records = get_audit_records(correlation_id=correlation_id)

        # Should get at least our 2 records
        assert len(records) >= 2
        assert all(r["correlation_id"] == correlation_id for r in records)

    def test_get_audit_records_respects_limit(self):
        """get_audit_records respects limit parameter."""
        records = get_audit_records(limit=3)

        assert len(records) <= 3


class TestAuditSchema:
    """Test audit record Pydantic schema."""

    def test_audit_record_schema_validates(self):
        """AuditRecordSchema validates correct data."""
        # Get a real audit record
        log_audit_record(
            correlation_id="test-schema-001",
            tool="sql",
            action="query",
            input_data={"q": "test"},
            output_data={"r": "result"},
            success=True,
            duration_ms=25
        )

        records = get_audit_records(correlation_id="test-schema-001")
        record_dict = records[0]

        # Should validate successfully
        schema = AuditRecordSchema(**record_dict)

        assert schema.correlation_id == "test-schema-001"
        assert schema.tool == "sql"
        assert schema.success is True

    def test_audit_record_schema_is_immutable(self):
        """AuditRecordSchema is frozen (immutable)."""
        schema = AuditRecordSchema(
            id=1,
            ts="2024-01-01T00:00:00Z",
            correlation_id="test",
            user_id=None,
            tool="sql",
            action="query",
            input_hash="a" * 64,
            output_hash="b" * 64,
            success=True,
            duration_ms=100
        )

        # Should not be able to modify
        with pytest.raises(Exception):
            schema.success = False
