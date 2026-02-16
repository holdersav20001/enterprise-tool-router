# AI Operating System (Repo Rules)

This repo is designed to be worked on with multiple coding assistants (Kimi / Claude Code / Codex) without context loss.

## Non-negotiables
- **Schema-first**: all agent outputs are validated by Pydantic models.
- **Eval-first**: changes should be measured using the eval harness (eval/).
- **No secrets/PII in logs**: log hashes/metadata, not raw sensitive content.
- **Small changes**: prefer commit-sized increments with clear messages.
- **Document decisions**: use ADRs in i/adr/.

## Using models intentionally
- **Kimi**: throughput (boilerplate, docs, tests, runbooks, repetitive refactors)
- **Claude Code**: design + security review + failure modes, sub-agents
- **Codex**: repo-native implementation, multi-file edits, PR-quality changes

## Workflow
Read i/workflow.md and follow the SPARC+TDD skill in i/skills/01_sparc_tdd.md.

## When pausing or switching model
Write a handoff doc in i/handoff/ using the template.
