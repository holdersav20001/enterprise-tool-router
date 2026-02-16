# ADR: Security Baseline (Week 1 plan)

## Context
We want enterprise credibility from day one; security cannot be retrofitted.

## Decision
Week 1: policies + scaffolding
Week 2+: implement:
- AuthN (JWT)
- AuthZ (tool/table allowlists)
- PII detection/redaction before logs + before LLM calls
- Audit logging (append-only) with correlation IDs

## Consequences
- Early design constraints prevent insecure patterns
