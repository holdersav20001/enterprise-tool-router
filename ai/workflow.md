# Working Method (Kimi / Claude / Codex)

## Default rules
1) Pick **one tool** for implementation for a given task (avoid mid-task switching).
2) Use SPARC+TDD: Spec â†’ Plan â†’ Act â†’ Review â†’ Check.
3) If switching models or stopping work: create a handoff doc.

## When to use what
### Kimi 2.5
- Generate golden test cases, runbooks, docs, boilerplate, repetitive refactors.
- Good for â€œexpand to 50 test casesâ€ or â€œwrite 10 runbooksâ€.

### Claude Code
- Threat model, security review, failure modes, reliability patterns.
- Use sub-agents stored as Markdown files in i/skills/.

### Codex
- Multi-file implementation tasks, refactors, PR-style cleanups.
- Prefer when you want â€œgo implement X across the repo safelyâ€.

## Definition of Done (per task)
- Tests added/updated
- Eval harness run locally (when applicable)
- ADR updated (if decision made)
- Short note in handoff if switching context
