# Enterprise Tool Router

A production-minded LLM tool router for enterprise questions that selects the right tool (SQL / retrieval / REST) with strict schemas, evaluation harness, and audit-ready engineering patterns.

## Quickstart (Windows PowerShell)
\\\powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -q
python -m enterprise_tool_router.main
\\\

## Roadmap (Week 1 complete)
- Repo hygiene, AI operating system (skills/runbooks/ADRs)
- FastAPI skeleton + schemas-first contracts
- Eval harness + golden dataset + CI gates
