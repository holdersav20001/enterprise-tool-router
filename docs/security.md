# Security Baseline - Enterprise Tool Router

## Overview

The Enterprise Tool Router implements a defense-in-depth security model with multiple layers of protection to prevent data loss, unauthorized access, and destructive operations.

## Threat Model

### Assets Protected
1. **Production Database**: PostgreSQL containing business-critical data
2. **Audit Trail**: Immutable log of all operations for compliance
3. **User Data**: Query inputs and results (potentially sensitive)
4. **API Credentials**: Database connection strings and passwords

### Threats Mitigated
1. **SQL Injection**: Malicious SQL via natural language queries
2. **Data Destruction**: Accidental or intentional DELETE/DROP operations
3. **Data Exfiltration**: Unbounded result sets (e.g., SELECT * without LIMIT)
4. **Audit Tampering**: Modification or deletion of audit records
5. **Unauthorized Access**: Unauthenticated API calls or database access

## Security Controls

### 1. SQL Safety Model (Multi-Layer Defense)

#### Layer 1: Query Type Restriction
**Control**: Only SELECT statements are permitted

**Bypasses Prevented**:
- Comments before SELECT
- Whitespace tricks
- Case variations

#### Layer 2: Query Chaining Prevention
**Control**: No semicolons allowed in queries
**Attack Prevented**: SELECT * FROM users; DROP TABLE users;

#### Layer 3: Dangerous Keyword Blocking
**Control**: Block INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, GRANT, REVOKE, COPY

**Why These Keywords**:
- Data Modification: INSERT, UPDATE, DELETE, TRUNCATE
- Schema Changes: CREATE, DROP, ALTER
- Privilege Escalation: GRANT, REVOKE
- Data Exfiltration: COPY

#### Layer 4: Enforced Result Limit
**Control**: Add LIMIT 200 if not present
**Protection**: Prevents SELECT * FROM billion_row_table

#### Layer 5: Table Allowlist
**Control**: Only permit queries against approved tables
**Allowlist**: sales_fact, job_runs, audit_log
**Why Allowlist**: Zero-trust model - explicit approval required

### 2. Database Access Control

#### Connection Security
- **Authentication**: scram-sha-256 password hashing (PostgreSQL 10+)
- **No Trust**: Removed trust auth method (insecure)
- **Least Privilege**: Database user etr_user has SELECT-only permissions
- **Network Isolation**: Docker network isolation

#### Port Configuration
- **Non-Standard Port**: 5433 (avoids conflict with local PostgreSQL on 5432)
- **Localhost Only**: Bound to 127.0.0.1
- **Environment Variables**: Credentials stored in environment, never hardcoded

### 3. Audit Logging (Tamper-Proof)

#### Append-Only Design
**Control**: Audit log table has no UPDATE/DELETE permissions
**Implementation**: INSERT-only operations
**Enforcement**: Database-level constraints

#### Input/Output Hashing
**Control**: SHA256 hash of all inputs and outputs
**Purpose**: Detect tampering, enable non-repudiation

**Guarantees**:
- Same input always produces same hash (reproducible)
- Any modification to input/output is detectable
- Cannot reverse-engineer original data from hash

#### Correlation ID Tracking
**Control**: Unique ID per request for distributed tracing
**Benefit**: Link audit records across microservices

### 4. Input Validation (Pydantic Schemas)

#### Type Safety
**Control**: All API inputs validated against Pydantic schemas

**Protection**:
- Reject empty queries
- Prevent excessively long queries (DoS)
- Enforce type constraints

#### Schema Immutability
**Control**: All Pydantic models are frozen (immutable)
**Rationale**: Prevent accidental modification after validation

### 5. Error Handling (Fail-Safe)

#### Safe Error Messages
**Control**: Never expose internal details in error responses

**Bad**: Error: syntax error at line 42 of /etc/passwd
**Good**: Query validation failed

## Security Testing

### Test Coverage
- **20 SQL safety tests**: Validate all 5 layers of SQL safety model
- **18 audit tests**: Verify append-only logging, hashing, context managers
- **5 schema tests**: Ensure Pydantic validation works correctly

### CI Quality Gates
- **Schema compliance**: 100% of responses must pass Pydantic validation
- **Accuracy**: 70% routing accuracy
- **Zero tolerance**: Any test failure blocks CI pipeline

## Compliance Considerations

### SOX/GDPR Alignment
1. **Audit Trail**: Immutable append-only log satisfies SOX requirements
2. **Data Hashing**: SHA256 hashing enables data integrity verification
3. **Correlation IDs**: Support incident investigation and forensics
4. **Access Control**: Least-privilege database permissions

## Known Limitations

### Current Gaps
1. **No Authentication**: API endpoints are not authenticated (planned: JWT/API keys)
2. **No Rate Limiting**: Susceptible to DoS via query flooding
3. **No TLS**: HTTP only, not HTTPS
4. **Cleartext Passwords**: Database password in environment
5. **No Query Logging**: SQL queries not logged separately

### Future Enhancements
1. **Row-Level Security**: PostgreSQL RLS policies for multi-tenant data
2. **Query Parameter Binding**: Use parameterized queries
3. **VPC Isolation**: Deploy database in private subnet
4. **Secrets Rotation**: Automatic password rotation
5. **WAF Integration**: Web Application Firewall for API protection

## Security Best Practices

### For Developers
1. **Never bypass safety checks**: Do not add --unsafe flags or skip validation
2. **Use environment variables**: Never hardcode credentials in code
3. **Test safety violations**: Add tests for each new safety rule
4. **Review ADRs**: Understand security trade-offs before changing design

### For Operators
1. **Monitor audit logs**: Set up alerts for suspicious patterns
2. **Rotate credentials**: Change database passwords regularly
3. **Review table allowlist**: Audit which tables are accessible
4. **Backup audit logs**: Archive audit_log table for long-term retention

## Incident Response

### Safety Violation Detected
1. **Alert**: Log warning with correlation_id and user_id
2. **Block**: Reject query immediately with error response
3. **Audit**: Record violation in audit_log (success=False)
4. **Investigate**: Review audit logs for patterns

### Suspected Data Breach
1. **Freeze**: Disable API or revoke database credentials
2. **Analyze**: Query audit_log for suspicious queries
3. **Contain**: Isolate affected systems, rotate all credentials
4. **Remediate**: Patch vulnerabilities, enhance safety rules

---

**Document Version**: 1.0  
**Last Updated**: 2026-02-16  
**Status**: Week 2 Complete (Commit 15)
