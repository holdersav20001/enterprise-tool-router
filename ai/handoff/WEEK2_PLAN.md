# Week 2 Plan  Enterprise Tool Router
Owner: James
Goal: Deliver a real SQL tool backed by Postgres with safe constraints, audit logging, and expanded evals. Keep code synchronous this week.

## Outcomes by end of Week 2
- Local Postgres via docker-compose with seed data
- SQL tool executes read-only queries safely (SELECT-only + allowlist + default LIMIT)
- Structured SQL result schema returned by API
- Audit log written for every /query call (append-only)
- Eval dataset expanded (10  25 cases) and CI gates enforce:
  - schema compliance = 100%
  - tool selection accuracy >= 0.70 (Week 2 target)
- Docs + ADR capture "why" decisions (safety model, audit model)

## Constraints (non-negotiable)
- Never log raw secrets or raw PII
- SQL tool is read-only: no DDL/DML; no multiple statements
- Prefer allowlists to denylists
- Keep commits small and reviewable (PR-sized)
- Update ADRs when a decision is made

## Commit plan (Week 2)
### Commit 09  Postgres local environment
Add:
- docker-compose.yml (postgres:16)
- sql/001_init.sql (schema + seed data)
- scripts/db_up.ps1 and scripts/db_down.ps1
Acceptance:
- docker compose up -d works
- psql can connect to db

### Commit 10  Wire SqlTool to Postgres (sync)
Add:
- src/enterprise_tool_router/db.py (connection helper)
- requirements update for psycopg (sync)
Change:
- SqlTool.run executes a safe query against Postgres
Safety rules:
- Only SELECT statements
- Block ';'
- Block keywords: INSERT/UPDATE/DELETE/CREATE/DROP/ALTER/TRUNCATE/GRANT/REVOKE/COPY
- Enforce LIMIT if absent (e.g. LIMIT 200)
- Table allowlist (Week 2: simple regex-based)
Acceptance:
- /query returns rows for seeded queries
- Unit tests cover SELECT-only + LIMIT enforcement

### Commit 11  Structured SQL tool output schema
Add:
- src/enterprise_tool_router/schemas_sql.py
Return:
- columns: list[str]
- rows: list[list[Any]]
- row_count: int
Acceptance:
- API returns stable schema (no raw driver objects)
- tests validate output schema

### Commit 12  Audit logging (append-only)
Add:
- src/enterprise_tool_router/audit.py
- sql migration: audit_log table
Change:
- /query logs an audit record with:
  - ts, correlation_id, user_id, tool, action, input_hash, output_hash, success, duration_ms
Acceptance:
- After calls, audit_log contains rows
- Tests validate hashing + insert call path

### Commit 13  Expand eval harness + golden set to 25 cases
Change:
- eval/golden_cases_v0.jsonl: 25 cases (12 sql, 8 vector, 5 rest)
- eval runner validates for SQL cases:
  - row_count > 0 for seeded queries
Acceptance:
- make eval produces report JSON in eval/reports/v0.json

### Commit 14  CI quality gates
Change:
- eval runner exits non-zero if:
  - schema_rate < 1.0
  - accuracy < 0.70
Acceptance:
- CI fails when gates fail

### Commit 15  Docs + ADR
Add:
- docs/architecture.md (Mermaid diagram updated for Postgres)
- docs/security-baseline.md (SQL safety rules + audit logging)
- ai/adr/0004-sql-tool-safety.md (decision record)
Acceptance:
- Documentation answers why this approach clearly

## Testing checklist (run before each commit)
- pytest -q
- python eval/runner.py --cases eval/golden_cases_v0.jsonl --out eval/reports/v0.json
- manual smoke: run API + curl /query

## Manual smoke commands
Start db:
- docker compose up -d

Run API:
- $env:PYTHONPATH="src"; python -m enterprise_tool_router.main

Call API:
- curl -Method POST http://127.0.0.1:8000/query -ContentType "application/json" -Body '{\"query\":\"Show me Q4 revenue by region\"}'

## Definition of Done (Week 2)
- SQL tool real + safe + tested
- Audit logging works
- Eval + CI gates in place
- Docs/ADR updated