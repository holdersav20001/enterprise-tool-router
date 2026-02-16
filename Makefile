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
