You are acting as a senior engineer contributing to this repo.

First, read and follow:
- ai/README.md
- ai/policy.md
- ai/workflow.md
- ai/skills/01_sparc_tdd.md
- ai/handoff/WEEK2_PLAN.md

Rules:
- Make changes as small, reviewable commits matching the commit plan in WEEK2_PLAN.md (Commit 09..15).
- For each commit: list files changed, commands to run, and acceptance checks.
- Keep code synchronous in Week 2.
- Enforce SQL safety (SELECT-only, no semicolons, deny DDL/DML keywords, add LIMIT if missing, allowlist tables).
- Add tests for safety and output schema.
- Update ADRs when decisions are made.

Start with Commit 09:
1) Create docker-compose.yml for Postgres 16.
2) Create sql/001_init.sql with schema + seed data (sales_fact, job_runs, audit_log).
3) Create scripts/db_up.ps1 and scripts/db_down.ps1.
4) Update README with DB startup instructions.

When done, stop and ask me to run the commands and confirm before proceeding to Commit 10.