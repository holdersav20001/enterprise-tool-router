[IO.File]::WriteAllText("$PWD\ai\handoff\WEEK3_PLAN.md", @"
# Week 3 Plan — Controlled LLM Integration
Owner: James
Goal: Introduce LLM-based SQL planning safely within deterministic guardrails.

---

# Week 3 Theme

LLM proposes.
Deterministic system approves.
System executes only validated SQL.

---

# Objectives

By end of Week 3:

- Natural language → SQL via LLM planner
- Structured JSON enforcement for LLM output
- Deterministic SQL validator gate remains authoritative
- Confidence threshold prevents unsafe execution
- Planner metrics added to eval harness
- Cost tracking integrated into audit

---

# Architecture Change

Old:
Query → Router → SQL Tool → DB

New:
Query
  ↓
Router (deterministic)
  ↓
SQL Planner (LLM)
  ↓
SQL Validator (Week 2 safety rules)
  ↓
SQL Tool (execution)
  ↓
DB

---

# Commit Plan

---

## Commit 16 — LLM Abstraction Layer

Add:
- src/enterprise_tool_router/llm/base.py
- src/enterprise_tool_router/llm/providers/anthropic.py
- src/enterprise_tool_router/llm/providers/openai.py

Requirements:
- Single interface: generate_structured(prompt, schema)
- Return parsed JSON only
- Track token usage and cost estimate
- Model selected via environment variable

Acceptance:
- Unit test using mock provider
- No LLM calls inside tools directly

---

## Commit 17 — SQL Planner

Add:
- src/enterprise_tool_router/sql_planner.py

Planner input:
- natural language query
- database schema description
- allowed tables

Planner output (strict schema):
{
  ""sql"": ""SELECT ... LIMIT 200"",
  ""confidence"": 0.0-1.0,
  ""explanation"": ""string""
}

Rules:
- Must always include LIMIT
- Must return JSON only
- Schema validated via Pydantic

Acceptance:
- Unit tests validate schema enforcement
- Invalid LLM JSON is rejected

---

## Commit 18 — Integrate Planner + Validator

Modify SQL tool flow:

If query is NOT raw SQL:
  → call planner
  → validate returned SQL via existing safety validator
  → execute only if valid

If validation fails:
  → reject execution
  → structured error response
  → audit logged as failure

Acceptance:
- Test malicious planner output blocked
- Test raw SQL still works
- Test NL query generates SQL and executes

---

## Commit 19 — Confidence Threshold

Add rule:
- If planner confidence < 0.7:
    - Do not execute
    - Return clarification response
    - Log as low-confidence event

Acceptance:
- Unit test for threshold
- Manual test returns safe response

---

## Commit 20 — Extend Evaluation Harness

Add:
- Planner output validation metrics
- Natural language → expected tool mapping cases
- Track:
    - planner structured output rate
    - planner validation rejection rate
    - routing accuracy

CI must fail if:
- Planner schema compliance < 100%
- SQL validator bypassed
- Routing accuracy < 80%

---

# Constraints

- SQL validator remains unchanged in authority.
- No direct execution of raw LLM SQL.
- No logging of raw prompts or raw SQL.
- Cost must be recorded in audit log.

---

# Manual Smoke Test

1. DB running
2. API running
3. Send:
   ""Show revenue by region for Q4""

Expected:
- LLM generates SQL
- Validator approves
- Structured SQL result returned
- Audit entry written
- Cost logged

---

# Definition of Done

- Natural language SQL works
- Malicious LLM output is blocked
- Confidence gating works
- Eval harness updated
- CI passes
- Architecture remains deterministic

"@, (New-Object System.Text.UTF8Encoding($false)))
