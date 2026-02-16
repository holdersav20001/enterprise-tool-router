# ADR 002: Append-Only Audit Logging

## Status
Accepted

## Context
For compliance (SOX, GDPR, PCI DSS) and incident response, we need an immutable audit trail of all database query operations.

Requirements:
1. Immutability - Cannot be modified after creation
2. Non-Repudiation - Prove specific query was executed
3. Forensics - Support post-incident investigation
4. Performance - Must not degrade query performance
5. Privacy - Avoid storing sensitive data in cleartext

## Decision
Implement append-only audit logging with:

1. Database Table - PostgreSQL audit_log table
2. Append-Only - No UPDATE/DELETE permissions
3. Hashed Data - SHA256 hash instead of cleartext
4. Context Manager - Automatic timing and error handling
5. Correlation IDs - UUID per request for tracing

### Schema
- ts, correlation_id, user_id, tool, action
- input_hash, output_hash (SHA256)
- success, duration_ms

## Consequences

### Positive
1. Tamper-Proof - Database-level immutability
2. Queryable - SQL queries for forensics
3. Fast - Hashing <5ms
4. Privacy-Preserving - Hashes do not expose data
5. Reliable - Context manager ensures logging

### Negative
1. Storage Growth - Requires archival strategy
2. Cannot Inspect - Hashes prevent viewing original data
3. Performance - Extra INSERT per query (~2-5ms)

## Alternatives Considered
- Application Log Files - Rejected (mutable, not queryable)
- Cleartext Storage - Rejected (privacy risk)
- Asymmetric Encryption - Rejected (complex, slow)
- Blockchain - Rejected (overkill)
- Async Logging - Deferred (can add later)

## Implementation
- File: src/enterprise_tool_router/audit.py
- Tests: tests/test_audit.py (18 tests)

---
**Date**: 2026-02-16  
**Status**: Implemented (Week 2)
