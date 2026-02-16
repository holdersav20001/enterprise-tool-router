# ADR 003: Deterministic Router Pattern

## Status
Accepted

## Context
The router needs to direct natural language queries to appropriate tools (SQL, Vector, REST) with requirements:
1. Fast (<5ms)
2. Predictable (deterministic)
3. Testable
4. Observable
5. Cost-Effective

## Decision
Implement deterministic keyword-matching router with no AI/LLM calls:

### Algorithm
1. Normalize Query - Lowercase, collapse whitespace
2. Match Keywords - Check tool-specific keywords
3. Calculate Confidence - Weighted sum
4. Select Tool - Highest confidence wins

### Keywords
- SQL: select, where, group by, revenue, sales, query
- Vector: search, find, documentation, runbook, procedure
- REST: api, http, endpoint, post, get, call

## Consequences

### Positive
1. Fast - <1ms latency
2. Deterministic - Reproducible
3. Testable - Easy unit tests
4. Zero Cost - No API fees
5. Debuggable - Clear confidence scores
6. Offline - No internet required

### Negative
1. Limited Accuracy - 70-80% vs 95% with LLM
2. Keyword Maintenance - Manual updates needed
3. No Learning - Cannot improve from feedback
4. False Positives - Keywords in wrong context

## Alternatives Considered
- LLM-Based Routing - Rejected (slow, expensive, non-deterministic)
- Local Fine-Tuned Model - Deferred (complex setup)
- Hybrid Rules + LLM - Future enhancement
- Zero-Shot Classification - Rejected (overkill)

## Implementation
- File: src/enterprise_tool_router/router.py
- Tests: eval/golden_cases_v0.jsonl (25 cases)
- Current Accuracy: 80% (exceeds 70% target)

## Future Evolution
1. Keyword Tuning
2. Weighted Keywords
3. Regex Patterns
4. Confidence Thresholds
5. Query Rewriting

---
**Date**: 2026-02-16  
**Status**: Implemented (Week 1), Validated (Week 2)
