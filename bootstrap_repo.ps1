param(
  [string]$ProjectName = "enterprise-tool-router",
  [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"

function WriteFile($Path, $Content) {
  $dir = Split-Path $Path -Parent
  if ($dir -and !(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
  Set-Content -Path $Path -Value $Content -Encoding UTF8
  Write-Host "Wrote $Path"
}

# --- Directories ---
$dirs = @(
  "src/enterprise_tool_router",
  "tests",
  "docs",
  "eval",
  "ai/skills",
  "ai/runbooks",
  "ai/handoff",
  "ai/adr",
  ".github/workflows",
  ".vscode"
)
foreach ($d in $dirs) { if (!(Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null } }

# --- .gitignore ---
WriteFile ".gitignore" @"
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Environments
.venv/
venv/
.env

# OS / editor
.DS_Store
.vscode/*
!.vscode/settings.json

# Logs / local artifacts
logs/
eval/reports/
"@

# --- README ---
WriteFile "README.md" @"
# Enterprise Tool Router

A production-minded LLM tool router for enterprise questions that selects the right tool (SQL / retrieval / REST) with strict schemas, evaluation harness, and audit-ready engineering patterns.

## Quickstart (Windows PowerShell)
\`\`\`powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -q
python -m enterprise_tool_router.main
\`\`\`

## Roadmap (Week 1 complete)
- Repo hygiene, AI operating system (skills/runbooks/ADRs)
- FastAPI skeleton + schemas-first contracts
- Eval harness + golden dataset + CI gates
"@

# --- VS Code settings ---
WriteFile ".vscode/settings.json" @"
{
  "python.defaultInterpreterPath": ".venv\\\\Scripts\\\\python.exe",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["-q"],
  "editor.formatOnSave": true,
  "files.trimTrailingWhitespace": true
}
"@

# --- Makefile (works in Git Bash / WSL; on pure PowerShell use the commands in README) ---
WriteFile "Makefile" @"
.PHONY: setup test lint type run eval

setup:
\tpython -m venv .venv
\t. .venv/bin/activate && pip install -r requirements-dev.txt

test:
\t. .venv/bin/activate && pytest -q

lint:
\t. .venv/bin/activate && ruff check .
\t. .venv/bin/activate && ruff format --check .

type:
\t. .venv/bin/activate && mypy src

run:
\t. .venv/bin/activate && python -m enterprise_tool_router.main

eval:
\t. .venv/bin/activate && python eval/runner.py --cases eval/golden_cases_v0.jsonl --out eval/reports/v0.json
"@

# --- requirements ---
WriteFile "requirements.txt" @"
fastapi==0.115.8
uvicorn[standard]==0.30.6
pydantic==2.10.6
prometheus-client==0.21.1
opentelemetry-api==1.30.0
opentelemetry-sdk==1.30.0
opentelemetry-instrumentation-fastapi==0.51b0
opentelemetry-instrumentation-requests==0.51b0
"@

WriteFile "requirements-dev.txt" @"
-r requirements.txt
pytest==8.3.4
pytest-asyncio==0.25.3
ruff==0.9.6
mypy==1.15.0
types-requests==2.32.0.20241016
"@

# --- AI Operating System ---
WriteFile "ai/README.md" @"
# AI Operating System (Repo Rules)

This repo is designed to be worked on with multiple coding assistants (Kimi / Claude Code / Codex) without context loss.

## Non-negotiables
- **Schema-first**: all agent outputs are validated by Pydantic models.
- **Eval-first**: changes should be measured using the eval harness (`eval/`).
- **No secrets/PII in logs**: log hashes/metadata, not raw sensitive content.
- **Small changes**: prefer commit-sized increments with clear messages.
- **Document decisions**: use ADRs in `ai/adr/`.

## Using models intentionally
- **Kimi**: throughput (boilerplate, docs, tests, runbooks, repetitive refactors)
- **Claude Code**: design + security review + failure modes, sub-agents
- **Codex**: repo-native implementation, multi-file edits, PR-quality changes

## Workflow
Read `ai/workflow.md` and follow the SPARC+TDD skill in `ai/skills/01_sparc_tdd.md`.

## When pausing or switching model
Write a handoff doc in `ai/handoff/` using the template.
"@

WriteFile "ai/policy.md" @"
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
"@

WriteFile "ai/workflow.md" @"
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
- Use sub-agents stored as Markdown files in `ai/skills/`.

### Codex
- Multi-file implementation tasks, refactors, PR-style cleanups.
- Prefer when you want â€œgo implement X across the repo safelyâ€.

## Definition of Done (per task)
- Tests added/updated
- Eval harness run locally (when applicable)
- ADR updated (if decision made)
- Short note in handoff if switching context
"@

# --- Handoff template ---
WriteFile "ai/handoff/TEMPLATE.md" @"
# Handoff

## Goal
(What are we trying to achieve?)

## Current status
- What works
- What doesn't
- Key files touched

## Changes made
- Commits / diffs / decisions

## Next steps (top 3)
1)
2)
3)

## Risks / unknowns
- ...

## How to run
- setup:
- tests:
- eval:
- run:
"@

# --- ADR template + initial ADRs ---
WriteFile "ai/adr/TEMPLATE.md" @"
# ADR: <Title>

## Context
(What problem are we solving?)

## Decision
(What did we choose?)

## Alternatives considered
- Option A:
- Option B:

## Consequences
- Positive:
- Negative:

## Follow-ups
- ...
"@

WriteFile "ai/adr/0001-stack-selection.md" @"
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
"@

WriteFile "ai/adr/0002-evaluation-strategy.md" @"
# ADR: Evaluation Strategy (Golden dataset + regression gates)

## Context
Agent systems are probabilistic; quality must be measurable and regressions must be caught.

## Decision
- Maintain JSONL golden datasets in `eval/`
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
"@

WriteFile "ai/adr/0003-security-baseline.md" @"
# ADR: Security Baseline (Week 1 plan)

## Context
We want enterprise credibility from day one; security cannot be retrofitted.

## Decision
Week 1: policies + scaffolding
Week 2+: implement:
- AuthN (JWT)
- AuthZ (tool/table allowlists)
- PII detection/redaction before logs + before LLM calls
- Audit logging (append-only) with correlation IDs

## Consequences
- Early design constraints prevent insecure patterns
"@

# --- Skills files ---
WriteFile "ai/skills/00_router.md" @"
# Skill: Router Engineer

You are implementing the enterprise tool router.

## Objectives
- Deterministic wrapper around probabilistic routing
- Strict schema outputs (Pydantic)
- Tool registry pattern
- Safe fallbacks and clear error contracts

## Output expectations
- Small PR-sized commits
- Tests included
- Update eval dataset when behaviour changes
"@

WriteFile "ai/skills/01_sparc_tdd.md" @"
# Skill: SPARC + TDD for Agentic Systems

## SPARC loop
1) Spec: inputs/outputs, constraints, failure modes
2) Plan: steps + tests + eval additions
3) Act: implement small
4) Review: security/observability/reliability
5) Check: run tests + eval, update docs

## TDD focus (agentic)
- Schema validation tests (always)
- Tool routing tests (golden dataset)
- Safety tests (PII redaction, permissions)
- Failure-mode tests (timeouts/fallbacks)
"@

WriteFile "ai/skills/02_security_review.md" @"
# Skill: Security Reviewer

Review changes for:
- secrets handling
- PII exposure in logs
- authN/authZ boundaries
- tool permission scoping
- injection risks (SQL, prompt, URLs)
- audit logging completeness (who/what/when)

Deliver:
- Findings (severity, evidence)
- Fix recommendations
- Any ADR updates required
"@

WriteFile "ai/skills/03_observability.md" @"
# Skill: Observability Engineer

Ensure:
- correlation IDs
- structured logs
- Prometheus metrics for latency + errors
- OpenTelemetry traces across API/router/tool calls
- clear debugging runbooks

Deliver:
- What to instrument
- Names/labels for metrics
- Example Grafana dashboard panels (later)
"@

WriteFile "ai/skills/04_eval_harness.md" @"
# Skill: Evaluation Harness Engineer

Maintain:
- golden datasets (JSONL)
- runner that reports tool accuracy + schema compliance
- regression threshold policy

Deliver:
- new test cases for new behaviour
- ensure eval is fast (<30s for small sets)
"@

WriteFile "ai/skills/05_repo_hygiene.md" @"
# Skill: Repo Hygiene

Ensure:
- consistent structure, naming
- lint/type/test commands documented
- ADR updates for decisions
- handoff docs when switching context
"@

# --- Runbooks ---
WriteFile "ai/runbooks/debugging.md" @"
# Debugging Runbook

## If tool routing seems wrong
- Run eval: `python eval/runner.py --cases eval/golden_cases_v0.jsonl`
- Inspect failures in `eval/reports/`
- Add/adjust golden cases and routing heuristics (Week 1) or prompts (Week 2+)

## If schema validation fails
- Identify which Pydantic model failed
- Add a failing unit test
- Fix response shaping to pass schema
"@

WriteFile "ai/runbooks/incidents.md" @"
# Incident Patterns (future-facing)

- Tool timeout -> circuit breaker -> fallback tool -> partial response
- Downstream 5xx -> retry with backoff -> degrade gracefully
- Suspected PII -> redact -> log metadata only -> block if policy requires
"@

# --- Docs: quality gates ---
WriteFile "docs/quality-gates.md" @"
# Quality Gates

Minimum:
- Schema compliance: 100%
- Tests pass
- Eval runs (at least v0)

Targets (Phase 1):
- Tool selection accuracy > 90% on golden set
- P95 latency < 2s (local baseline)
"@

# --- FastAPI skeleton + logging ---
WriteFile "src/enterprise_tool_router/__init__.py" @"
__all__ = []
"@

WriteFile "src/enterprise_tool_router/config.py" @"
from pydantic import BaseModel

class Settings(BaseModel):
    service_name: str = "enterprise-tool-router"
    environment: str = "dev"

settings = Settings()
"@

WriteFile "src/enterprise_tool_router/logging.py" @"
import logging
import uuid
from fastapi import Request

logger = logging.getLogger(\"enterprise_tool_router\")

def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=\"%(asctime)s %(levelname)s %(message)s\",
    )

async def correlation_id_middleware(request: Request, call_next):
    cid = request.headers.get(\"x-correlation-id\") or str(uuid.uuid4())
    request.state.correlation_id = cid
    response = await call_next(request)
    response.headers[\"x-correlation-id\"] = cid
    return response
"@

WriteFile "src/enterprise_tool_router/schemas.py" @"
from pydantic import BaseModel, Field
from typing import Any, Literal, Optional

ToolName = Literal[\"sql\", \"vector\", \"rest\", \"unknown\"]

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    user_id: Optional[str] = None

class QueryResponse(BaseModel):
    tool_used: ToolName
    confidence: float = Field(..., ge=0.0, le=1.0)
    result: Any
    trace_id: str
    cost_usd: float = 0.0
    notes: Optional[str] = None
"@

WriteFile "src/enterprise_tool_router/tools/base.py" @"
from dataclasses import dataclass
from typing import Protocol, Any

@dataclass(frozen=True)
class ToolResult:
    data: Any
    notes: str = \"\"

class Tool(Protocol):
    name: str
    def run(self, query: str) -> ToolResult: ...
"@

WriteFile "src/enterprise_tool_router/tools/sql.py" @"
from .base import ToolResult

class SqlTool:
    name = \"sql\"

    def run(self, query: str) -> ToolResult:
        # Week 1: stub (no DB wiring yet)
        return ToolResult(data={\"message\": \"SQL tool stub\", \"query\": query})
"@

WriteFile "src/enterprise_tool_router/tools/vector.py" @"
from .base import ToolResult

class VectorTool:
    name = \"vector\"

    def run(self, query: str) -> ToolResult:
        # Week 1: stub
        return ToolResult(data={\"message\": \"Vector tool stub\", \"query\": query})
"@

WriteFile "src/enterprise_tool_router/tools/rest.py" @"
from .base import ToolResult

class RestTool:
    name = \"rest\"

    def run(self, query: str) -> ToolResult:
        # Week 1: stub
        return ToolResult(data={\"message\": \"REST tool stub\", \"query\": query})
"@

WriteFile "src/enterprise_tool_router/router.py" @"
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Dict, Tuple

from .schemas import ToolName
from .tools.sql import SqlTool
from .tools.vector import VectorTool
from .tools.rest import RestTool
from .tools.base import ToolResult

@dataclass
class Routed:
    tool: ToolName
    confidence: float
    result: ToolResult
    elapsed_ms: float

class ToolRouter:
    def __init__(self) -> None:
        self.tools: Dict[ToolName, object] = {
            \"sql\": SqlTool(),
            \"vector\": VectorTool(),
            \"rest\": RestTool(),
        }

    def route(self, query: str) -> Tuple[ToolName, float]:
        # Week 1 deterministic heuristic router (LLM comes Week 2)
        q = query.lower()
        if any(k in q for k in [\"select\", \"from\", \"group by\", \"revenue\", \"count\", \"sum\"]) or \"sql\" in q:
            return \"sql\", 0.75
        if any(k in q for k in [\"runbook\", \"docs\", \"how do i\", \"procedure\", \"playbook\"]) or \"doc\" in q:
            return \"vector\", 0.70
        if any(k in q for k in [\"call api\", \"endpoint\", \"http\", \"status\", \"service\"]) or \"api\" in q:
            return \"rest\", 0.70
        return \"unknown\", 0.30

    def handle(self, query: str) -> Routed:
        start = time.perf_counter()
        tool_name, conf = self.route(query)
        if tool_name == \"unknown\":
            res = ToolResult(data={\"message\": \"No confident tool match\", \"query\": query}, notes=\"unknown\")
        else:
            res = self.tools[tool_name].run(query)  # type: ignore[index]
        elapsed = (time.perf_counter() - start) * 1000
        return Routed(tool=tool_name, confidence=conf, result=res, elapsed_ms=elapsed)
"@

WriteFile "src/enterprise_tool_router/main.py" @"
from fastapi import FastAPI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

from .logging import setup_logging, correlation_id_middleware
from .schemas import QueryRequest, QueryResponse
from .router import ToolRouter

setup_logging()
app = FastAPI(title=\"Enterprise Tool Router\", version=\"0.1.0\")
app.middleware(\"http\")(correlation_id_middleware)

router = ToolRouter()

REQS = Counter(\"router_requests_total\", \"Total requests\", [\"tool\"])
LAT = Histogram(\"router_request_duration_ms\", \"Request duration in ms\")

@app.get(\"/health\")
def health():
    return {\"status\": \"ok\"}

@app.get(\"/metrics\")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post(\"/query\", response_model=QueryResponse)
def query(req: QueryRequest):
    routed = router.handle(req.query)
    REQS.labels(tool=routed.tool).inc()
    LAT.observe(routed.elapsed_ms)
    trace_id = getattr(req, \"user_id\", None) or \"local\"
    return QueryResponse(
        tool_used=routed.tool,
        confidence=routed.confidence,
        result=routed.result.data,
        trace_id=trace_id,
        cost_usd=0.0,
        notes=routed.result.notes or None,
    )

if __name__ == \"__main__\":
    import uvicorn
    uvicorn.run(\"enterprise_tool_router.main:app\", host=\"127.0.0.1\", port=8000, reload=True)
"@

# --- Tests ---
WriteFile "tests/test_smoke.py" @"
from enterprise_tool_router.router import ToolRouter

def test_router_instantiates():
    r = ToolRouter()
    assert r is not None

def test_routing_sql():
    r = ToolRouter()
    tool, conf = r.route(\"Show revenue by region\")
    assert tool == \"sql\"
    assert conf > 0.5

def test_routing_vector():
    r = ToolRouter()
    tool, conf = r.route(\"Show me the runbook for CDC failures\")
    assert tool == \"vector\"
    assert conf > 0.5

def test_routing_rest():
    r = ToolRouter()
    tool, conf = r.route(\"Call API endpoint status for service X\")
    assert tool == \"rest\"
    assert conf > 0.5
"@

# --- Eval harness ---
WriteFile "eval/golden_cases_v0.jsonl" @"
{\"id\":\"sql_001\",\"input\":\"Show me Q4 revenue by region\",\"expected_tool\":\"sql\"}
{\"id\":\"sql_002\",\"input\":\"Count number of failed jobs in the last 24 hours\",\"expected_tool\":\"sql\"}
{\"id\":\"sql_003\",\"input\":\"Sum gross premium by day\",\"expected_tool\":\"sql\"}
{\"id\":\"sql_004\",\"input\":\"Write SQL to group by product and count policies\",\"expected_tool\":\"sql\"}
{\"id\":\"vec_001\",\"input\":\"Where is the runbook for schema mismatch incidents?\",\"expected_tool\":\"vector\"}
{\"id\":\"vec_002\",\"input\":\"How do I handle CDC duplicate events? Check docs\",\"expected_tool\":\"vector\"}
{\"id\":\"vec_003\",\"input\":\"Show me the procedure/playbook for ledger adjustment failures\",\"expected_tool\":\"vector\"}
{\"id\":\"rest_001\",\"input\":\"Call API to check service health\",\"expected_tool\":\"rest\"}
{\"id\":\"rest_002\",\"input\":\"Hit HTTP endpoint /status for payments service\",\"expected_tool\":\"rest\"}
{\"id\":\"rest_003\",\"input\":\"Use API to fetch current queue depth\",\"expected_tool\":\"rest\"}
"@.Trim() + "`n"

WriteFile "eval/metrics.py" @"
from dataclasses import dataclass

@dataclass
class EvalResult:
    total: int
    correct: int
    accuracy: float
    schema_ok: int
    schema_rate: float

def summarize(total: int, correct: int, schema_ok: int) -> EvalResult:
    acc = (correct / total) if total else 0.0
    srate = (schema_ok / total) if total else 0.0
    return EvalResult(total=total, correct=correct, accuracy=acc, schema_ok=schema_ok, schema_rate=srate)
"@

WriteFile "eval/runner.py" @"
import argparse
import json
import time
from pathlib import Path

from pydantic import ValidationError
from enterprise_tool_router.router import ToolRouter
from enterprise_tool_router.schemas import QueryResponse
from eval.metrics import summarize

def read_jsonl(path: Path):
    for line in path.read_text(encoding=\"utf-8\").splitlines():
        if line.strip():
            yield json.loads(line)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(\"--cases\", required=True)
    ap.add_argument(\"--out\", required=False, default=None)
    args = ap.parse_args()

    router = ToolRouter()
    cases = list(read_jsonl(Path(args.cases)))

    total = 0
    correct = 0
    schema_ok = 0
    failures = []

    for c in cases:
        total += 1
        start = time.perf_counter()
        routed = router.handle(c[\"input\"])
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Build a response object like the API would
        try:
            resp = QueryResponse(
                tool_used=routed.tool,
                confidence=routed.confidence,
                result=routed.result.data,
                trace_id=\"eval\",
                cost_usd=0.0,
                notes=routed.result.notes or None,
            )
            schema_ok += 1
        except ValidationError as e:
            failures.append({\"id\": c[\"id\"], \"error\": \"schema\", \"detail\": str(e)})

        if routed.tool == c[\"expected_tool\"]:
            correct += 1
        else:
            failures.append({
                \"id\": c[\"id\"],
                \"error\": \"tool_mismatch\",
                \"expected\": c[\"expected_tool\"],
                \"got\": routed.tool,
                \"elapsed_ms\": elapsed_ms
            })

    summary = summarize(total, correct, schema_ok)
    report = {
        \"summary\": summary.__dict__,
        \"failures\": failures[:50],
    }

    print(json.dumps(report, indent=2))

    if args.out:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(report, indent=2), encoding=\"utf-8\")

    # basic gate: schema must be 100% in Week 1
    if summary.schema_rate < 1.0:
        raise SystemExit(\"Schema compliance gate failed\")

if __name__ == \"__main__\":
    main()
"@

# --- CI workflow ---
WriteFile ".github/workflows/ci.yml" @"
name: ci
on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt
      - name: Tests
        run: pytest -q
      - name: Eval
        run: python eval/runner.py --cases eval/golden_cases_v0.jsonl --out eval/reports/v0.json
"@

Write-Host "`nBootstrap complete."
Write-Host "Next:"
Write-Host "  python -m venv .venv"
Write-Host "  . .\\.venv\\Scripts\\Activate.ps1"
Write-Host "  pip install -r requirements-dev.txt"
Write-Host "  pytest -q"
Write-Host "  python -m enterprise_tool_router.main"
