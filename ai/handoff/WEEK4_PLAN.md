[IO.File]::WriteAllText("$PWD\ai\handoff\WEEK4_PLAN.md", @"
# Week 4 Plan — Resilience, Observability, Cost Control
Owner: James
Goal: Harden the Enterprise Tool Router for production-grade LLM reliability.

---

# Week 4 Theme

Make the system robust, measurable, and safe under load.

---

# Objectives

By end of Week 4:

- Add LLM timeout protection
- Add circuit breaker for LLM failures
- Add rate limiting (per user / IP)
- Add Redis caching for safe SQL responses
- Add structured error taxonomy
- Add token usage metrics + cost tracking
- Add shadow evaluation mode
- Extend CI to include regression drift check

---

# Commit Plan

---

## Commit 21 — LLM Timeout + Cancellation

Add:
- Timeout wrapper around LLM calls (configurable)
- Graceful fallback if timeout occurs
- Proper error classification (TimeoutError vs PlannerError)

Acceptance:
- Simulated slow LLM call returns safe error
- System does not hang
- Unit tests cover timeout

---

## Commit 22 — Circuit Breaker (LLM)

Add:
- Failure counter for planner
- Threshold (e.g., 5 failures in 1 min)
- Temporarily disable LLM planner
- Fallback to deterministic router

Acceptance:
- Simulate repeated planner failure
- Circuit opens
- System continues operating safely

---

## Commit 23 — Redis Caching Layer

Add:
- Cache for validated SQL responses
- Cache key: hash(query + tool)
- TTL configurable
- Only cache successful safe SQL responses

Acceptance:
- Second identical query hits cache
- No LLM call on cached hit
- Metrics reflect cache hit ratio

---

## Commit 24 — Rate Limiting

Add:
- Per-IP or per-user rate limit
- Reject excessive requests gracefully
- Log rate limit events

Acceptance:
- Load test triggers limit
- Returns structured error

---

## Commit 25 — Structured Error Taxonomy

Add:
- Custom error classes:
    - PlannerError
    - ValidationError
    - ExecutionError
    - TimeoutError
    - RateLimitError
- Ensure all errors return structured JSON

Acceptance:
- All errors return predictable schema
- Tests validate structure

---

## Commit 26 — Token + Cost Metrics

Extend:
- Prometheus metrics for:
    - tokens_input
    - tokens_output
    - cost_estimate
    - planner_latency
- Log cost per request in audit table

Acceptance:
- Metrics endpoint exposes cost data
- Audit log includes cost_usd

---

## Commit 27 — Shadow Evaluation Mode

Add:
- Ability to run planner in "shadow mode"
- Compare:
    - current SQL
    - alternative planner SQL
- Log diff without executing

Acceptance:
- Shadow mode logs comparison
- No execution impact

---

# Definition of Done

- LLM failures do not break system
- Cache reduces repeated LLM calls
- Rate limiting prevents abuse
- All errors structured
- Cost measurable
- Shadow mode operational
- CI passes with regression gate

"@, (New-Object System.Text.UTF8Encoding($false)))
