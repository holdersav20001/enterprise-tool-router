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

## Database Setup (Week 2)

The SQL tool requires a Postgres database. Start it with Docker:

\\\powershell
# Start the database (Postgres 16)
. .\scripts\db_up.ps1

# Stop the database (preserves data)
. .\scripts\db_down.ps1

# Stop and remove all data (WARNING: irreversible)
. .\scripts\db_down.ps1 -Volumes
\\\

Connection details:
- Host: localhost, Port: 5432
- Database: etr_db
- Username: etr_user / Password: etr_password

Connect manually:
\\\powershell
docker exec -it etr-postgres psql -U etr_user -d etr_db
\\\

## Roadmap (Week 1 complete)
- Repo hygiene, AI operating system (skills/runbooks/ADRs)
- FastAPI skeleton + schemas-first contracts
- Eval harness + golden dataset + CI gates
