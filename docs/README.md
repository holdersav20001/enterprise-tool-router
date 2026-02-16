# Documentation Index

Welcome to the Enterprise Tool Router documentation.

## Quick Links

- **[Architecture](architecture.md)** - System architecture, component diagrams, and data flow
- **[Security](security.md)** - Security baseline, threat model, and controls
- **[Architecture Decision Records (ADRs)](adr/)** - Key design decisions and trade-offs

## Architecture Decision Records

ADRs document important architectural decisions made during development:

- **[ADR 001: SQL Safety Model](adr/001-sql-safety-model.md)** - Multi-layer defense for SQL query execution
- **[ADR 002: Append-Only Audit Logging](adr/002-append-only-audit-logging.md)** - Immutable audit trail design
- **[ADR 003: Deterministic Router Pattern](adr/003-deterministic-router-pattern.md)** - Keyword-based routing (no LLM)

## Document Structure

### Architecture (architecture.md)
- System overview and component diagrams
- Query flow sequences
- Technology stack
- Design principles
- Performance characteristics

### Security (security.md)
- Threat model
- Security controls (5-layer SQL safety)
- Database access control
- Audit logging
- Compliance considerations
- Incident response procedures

### ADRs (adr/)
Each ADR follows a standard format:
- **Status** - Proposed, Accepted, Deprecated, Superseded
- **Context** - Problem and constraints
- **Decision** - Chosen solution
- **Consequences** - Positive, negative, and trade-offs
- **Alternatives** - Options considered and rejected
- **Implementation** - Where to find the code

## Contributing

When making architectural changes:
1. Review existing ADRs for precedent
2. Create new ADR if decision impacts architecture
3. Update architecture.md diagrams if needed
4. Update security.md if security posture changes

## Version History

- **v1.0** (2026-02-16) - Initial documentation for Week 2 delivery
  - Architecture diagrams with Mermaid
  - Security baseline with 5-layer SQL safety model
  - 3 ADRs covering core design decisions

---

**Last Updated**: 2026-02-16  
**Status**: Week 2 Complete
