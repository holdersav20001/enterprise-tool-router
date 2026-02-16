# Product Requirements Document (PRD)
## Enterprise Tool Router
Version: 0.1  
Owner: James  
Status: Active Development  

---

# 1. Overview

The Enterprise Tool Router is a production-oriented API service that routes business queries to deterministic backend tools (SQL / Retrieval / REST) under strict safety, audit, and evaluation controls.

This is **not** a chatbot.

It is an enterprise-safe orchestration foundation for agentic systems.

The system enforces deterministic boundaries around probabilistic routing decisions and ensures auditability, structured outputs, and measurable quality.

---

# 2. Objectives

By completing Application 1, the system must:

- Route queries to appropriate tools
- Execute SQL safely against Postgres (read-only)
- Produce structured outputs
- Log all actions in an append-only audit log
- Provide observability via metrics
- Enforce evaluation quality gates in CI
- Be demonstrable end-to-end

---

# 3. Problem Statement

Enterprise AI systems fail because they:

- Lack structured output guarantees
- Do not enforce safe tool boundaries
- Have no audit trail
- Cannot measure regression
- Mix probabilistic reasoning with unsafe execution

This application solves this by:

Wrapping tool routing inside deterministic infrastructure with enforceable safety policies.

---

# 4. Scope

## In Scope

- FastAPI service
- /query endpoint
- Tool routing layer
- SQL tool (read-only, allowlisted)
- Retrieval tool (stub)
- REST tool (stub)
- Postgres integration
- Structured SQL response schema
- Append-only audit logging
- Evaluation harness (golden dataset)
- CI quality gates
- Prometheus metrics
- Correlation IDs

## Out of Scope (Future)

- Multi-agent orchestration
- JWT auth (future phase)
- Role-based access control
- Circuit breakers
- Canary deployments
- Self-healing pipelines

---

# 5. Functional Requirements

## FR1  Query Endpoint

POST /query

Input:
{
  "query": "Show revenue by region",
  "user_id": "optional"
}

Output:
{
  "tool_used": "sql",
  "confidence": 0.75,
  "result": {
    "columns": ["region", "revenue"],
    "rows": [["EU", 1200000]],
    "row_count": 1
  },
  "trace_id": "uuid",
  "cost_usd": 0.0,
  "notes": null
}

---

## FR2  Tool Routing

- Router selects tool deterministically (initially keyword-based).
- Returns tool name + confidence.
- Unknown tool results in safe fallback.
- No implicit execution of undefined tools.

---

## FR3  SQL Tool

The SQL tool must:

- Connect to Postgres via environment variables.
- Execute only SELECT statements.
- Reject:
  - Multiple statements
  - Semicolons
  - DDL/DML keywords:
    INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, TRUNCATE, GRANT, REVOKE, COPY
- Enforce default LIMIT 200 if absent.
- Restrict access to allowlisted tables:
  - sales_fact
  - job_runs
  - audit_log (read-only; future restriction possible)
- Return structured result:
  - columns (list[str])
  - rows (list[list[Any]])
  - row_count (int)

Raw driver objects must never be returned.

---

## FR4  SQL Safety Model

- Prefer allowlists over denylists.
- No raw SQL logged anywhere.
- Query must be validated before execution.
- Safety checks must be unit testable independent of live DB.

---

## FR5  Audit Logging

Every /query call must log:

- timestamp
- correlation_id
- user_id
- tool_used
- input_hash (SHA256)
- output_hash (SHA256)
- success flag
- duration_ms

Audit table must be append-only.

No raw query or raw result may be stored.

---

## FR6  Evaluation Harness

Maintain golden dataset in JSONL format.

Eval must measure:

- Tool selection accuracy
- Schema compliance rate
- Failure breakdown

CI must fail if:

- Schema compliance < 100%
- Accuracy < threshold (0.70 in Week 2; 0.90 later)

---

## FR7  Observability

Expose Prometheus metrics:

- Request count
- Latency histogram
- Tool usage distribution

All requests must include correlation IDs.

Structured logging required.

---

# 6. Non-Functional Requirements

## NFR1  Deterministic Boundaries

All side effects must be deterministic.

Probabilistic decisions must:
- Be measurable
- Be validated
- Produce structured output

---

## NFR2  Security Baseline

- No secrets in code
- Environment-based configuration
- No sensitive data in logs
- Strict SQL safety enforcement

---

## NFR3  Testability

- Unit tests must pass without live DB.
- SQL validation logic must be independently testable.
- Eval harness must run locally.
- CI must enforce gates.

---

## NFR4  Performance

- P95 latency < 2s (local baseline)
- Default SQL LIMIT prevents unbounded queries
- Eval suite runs < 30 seconds

---

# 7. Architecture

Client  
    
FastAPI API  
    
Router  
    
Tool (SQL / Retrieval / REST)  
    
Postgres  

Audit log + Metrics wrap entire flow.

---

# 8. Definition of Done (Application 1)

The system is complete when:

- Postgres runs via docker-compose
- API runs via VS Code task
- SQL queries execute safely
- Structured outputs returned
- Audit entries recorded
- Eval harness passes
- CI gates enforced
- Safety model can be clearly explained

---

# 9. Engineering Process

All implementation must:

- Follow SPARC + TDD
- Be incremental and commit-scoped
- Update ADRs when decisions are made
- Update golden dataset when behaviour changes
- Never introduce unsafe SQL execution

---

# 10. Risks & Mitigations

Risk: SQL injection  
Mitigation: SELECT-only + allowlist + validation layer

Risk: Data mutation  
Mitigation: Reject all DML/DDL

Risk: Regression  
Mitigation: Eval harness + CI gate

Risk: Silent failure  
Mitigation: Audit logging + metrics

---

# 11. Target Audience

- Enterprise AI architects
- Regulated financial environments
- Consulting demonstrations
- Technical interview discussions
- Foundation for multi-agent systems

---

# 12. Claude Execution Directive

When implementing this PRD:

- Follow ai/workflow.md
- Apply ai/skills/01_sparc_tdd.md
- Implement incrementally using WEEK2_PLAN.md commit structure
- Do not bypass safety constraints
- Stop after each commit for verification