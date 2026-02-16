# ADR: Evaluation Strategy (Golden dataset + regression gates)

## Context
Agent systems are probabilistic; quality must be measurable and regressions must be caught.

## Decision
- Maintain JSONL golden datasets in eval/
- Measure:
  - tool selection accuracy
  - schema compliance
  - latency (basic timing)
- Add CI gate: fail if score drops beyond threshold (later)

## Alternatives considered
- Manual testing only (insufficient)
- LLM-as-judge only (useful later but not enough alone)

## Consequences
- Extra upfront work
- Much higher confidence in changes over time
