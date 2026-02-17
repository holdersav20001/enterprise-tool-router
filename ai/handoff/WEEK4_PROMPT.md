[IO.File]::WriteAllText("$PWD\ai\handoff\WEEK4_PROMPT.md", @"
You are contributing as a senior engineer.

Read:

- docs/PRD.md
- ai/workflow.md
- ai/policy.md
- ai/skills/01_sparc_tdd.md
- ai/handoff/WEEK4_PLAN.md

Rules:

- Follow Commit 21–27 structure.
- Small incremental commits.
- Preserve deterministic SQL validator authority.
- No unsafe execution paths.
- All new features must be testable without live LLM.
- Add unit tests before integration.
- Do not log raw SQL or raw prompts.

Start with Commit 21 (LLM Timeout + Cancellation).
Stop after each commit and request verification.

"@, (New-Object System.Text.UTF8Encoding($false)))
