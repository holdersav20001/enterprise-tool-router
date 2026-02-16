# Engineering Policy

## Safety & Compliance
- Never log secrets, tokens, or raw PII.
- Prefer allowlists to denylists (tools, tables, routes).
- All tool execution must be permission-scoped (read-only by default).

## Quality Gates
- JSON schema compliance: **100%**
- Regression: fail CI if eval score drops >5%
- Every endpoint must have tests for:
  - schema validation
  - authz decisions (when added)
  - failure mode behaviour (timeouts/fallback)

## Observability
- Correlation IDs everywhere
- Metrics: latency, tool success rate, schema compliance, token/cost (when LLM added)
- Traces: API â†’ router â†’ tool

## Change Management
- ADR required for meaningful architectural decisions
- Prefer feature flags / kill switches for risky behaviour
