# ADR 001: SQL Safety Model

## Status
Accepted

## Context
The Enterprise Tool Router needs to execute SQL queries generated from natural language inputs. This presents significant security risks including SQL injection, data loss, data exfiltration, and privilege escalation.

Traditional parameterized queries are insufficient because natural language queries are converted to SQL dynamically.

## Decision
We implement a multi-layer SQL safety model with five independent controls:

### Layer 1: Query Type Restriction
- Only SELECT statements permitted

### Layer 2: Query Chaining Prevention
- No semicolons allowed

### Layer 3: Dangerous Keyword Blocking
- Blocklist: INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, GRANT, REVOKE, COPY

### Layer 4: Enforced Result Limit
- Add LIMIT 200 if missing

### Layer 5: Table Allowlist
- Only sales_fact, job_runs, audit_log accessible

## Consequences

### Positive
1. Defense in Depth - Five independent layers
2. Fail-Safe - Each layer independently rejects unsafe queries
3. Testable - Each layer has dedicated unit tests
4. Performance - All checks <1ms overhead

### Negative
1. Limited Functionality - Cannot support INSERT/UPDATE/DELETE
2. False Positives - Some legitimate queries rejected
3. Maintenance Burden - New SQL features require safety review

## Alternatives Considered
- Parameterized Queries Only - Rejected (cannot handle dynamic queries)
- SQL Parsing with AST - Rejected (complex, error-prone)
- Database Read-Only User - Rejected as sole control
- LLM-Based Validation - Rejected (non-deterministic, slow)

## Implementation
- File: src/enterprise_tool_router/tools/sql.py
- Tests: tests/test_sql_safety.py (11 tests)

---
**Date**: 2026-02-16  
**Status**: Implemented (Week 2)
