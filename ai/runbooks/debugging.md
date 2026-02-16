# Debugging Runbook

## If tool routing seems wrong
- Run eval: python eval/runner.py --cases eval/golden_cases_v0.jsonl
- Inspect failures in eval/reports/
- Add/adjust golden cases and routing heuristics (Week 1) or prompts (Week 2+)

## If schema validation fails
- Identify which Pydantic model failed
- Add a failing unit test
- Fix response shaping to pass schema
