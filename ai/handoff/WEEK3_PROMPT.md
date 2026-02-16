[IO.File]::WriteAllText("$PWD\ai\handoff\WEEK3_PROMPT.md", @"
You are contributing to this repository as a senior engineer.

Before making changes, read:

- docs/PRD.md
- ai/workflow.md
- ai/policy.md
- ai/skills/01_sparc_tdd.md
- ai/handoff/WEEK3_PLAN.md

Rules:

- Follow the commit structure defined in WEEK3_PLAN.md (Commit 16–20).
- Make small, reviewable changes.
- Apply SPARC + TDD.
- LLM must only propose SQL; deterministic validator must approve.
- All LLM outputs must be structured JSON validated via schema.
- Do not bypass safety constraints.
- Do not log raw SQL or prompts.

Start with Commit 16:

1. Create LLM abstraction layer.
2. Add provider structure.
3. Add mock-based unit tests.
4. Stop and request verification before moving to Commit 17.

"@, (New-Object System.Text.UTF8Encoding($false)))
