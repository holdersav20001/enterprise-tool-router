# Incident Patterns (future-facing)

- Tool timeout -> circuit breaker -> fallback tool -> partial response
- Downstream 5xx -> retry with backoff -> degrade gracefully
- Suspected PII -> redact -> log metadata only -> block if policy requires
