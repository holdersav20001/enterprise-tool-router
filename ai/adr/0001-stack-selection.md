# ADR: Stack Selection (FastAPI + Postgres/pgvector + Redis + OTel + Prometheus)

## Context
We need a production-minded tool router with enterprise-friendly primitives.

## Decision
- FastAPI for API + typed contracts
- Postgres for state + pgvector for retrieval (single DB footprint)
- Redis later for caching/rate limiting/queues
- OpenTelemetry for distributed traces
- Prometheus/Grafana for metrics dashboards

## Alternatives considered
- LangChain-first approach (too much abstraction early)
- Separate vector DB (Pinecone/Weaviate) (extra moving parts in Week 1)

## Consequences
- Faster iteration and fewer components initially
- Clear upgrade path to managed services later
