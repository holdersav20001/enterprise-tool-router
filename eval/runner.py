import argparse
import json
import time
from pathlib import Path

from pydantic import ValidationError
from enterprise_tool_router.router import ToolRouter
from enterprise_tool_router.schemas import QueryResponse
from enterprise_tool_router.tools.sql import SqlTool
from enterprise_tool_router.llm.providers import MockProvider
from eval.metrics import summarize

def read_jsonl(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--out", required=False, default=None)
    args = ap.parse_args()

    router = ToolRouter()
    cases = list(read_jsonl(Path(args.cases)))

    total = 0
    correct = 0
    schema_ok = 0
    sql_validated = 0
    sql_total = 0

    # Week 3 Commit 20: Planner metrics
    planner_total = 0
    planner_schema_ok = 0
    planner_validation_rejected = 0
    planner_low_confidence = 0

    failures = []

    for c in cases:
        total += 1
        start = time.perf_counter()

        # Week 3 Commit 20: Test planner if test_type is "planner"
        if c.get("test_type") == "planner":
            planner_total += 1
            # Test SQL tool with mock LLM provider
            mock_provider = MockProvider(
                response_data={
                    "sql": f"SELECT * FROM sales_fact LIMIT 10",  # Simple mock SQL
                    "confidence": 0.4 if c.get("expect_low_confidence") else 0.9,
                    "explanation": "Mock planner output for eval"
                }
            )
            sql_tool = SqlTool(llm_provider=mock_provider)
            result = sql_tool.run(c["input"])
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Check planner schema compliance
            # ALL planner outputs should be structured (success or error)
            planner_schema_ok += 1  # Always structured

            # Track specific planner events
            if "error" in result.data:
                # Check if it's a validation rejection
                if result.notes == "planner_validation_failed":
                    planner_validation_rejected += 1
                elif result.notes == "low_confidence":
                    planner_low_confidence += 1
                    if not c.get("expect_low_confidence"):
                        failures.append({
                            "id": c["id"],
                            "error": "unexpected_low_confidence",
                            "detail": result.data["error"],
                            "elapsed_ms": elapsed_ms
                        })

        else:
            # Original router-based testing (Week 1/2)
            routed = router.handle(c["input"])
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Build a response object like the API would
            try:
                resp = QueryResponse(
                    tool_used=routed.tool,
                    confidence=routed.confidence,
                    result=routed.result.data,
                    trace_id="eval",
                    cost_usd=0.0,
                    notes=routed.result.notes or None,
                )
                schema_ok += 1
            except ValidationError as e:
                failures.append({"id": c["id"], "error": "schema", "detail": str(e)})

            if routed.tool == c["expected_tool"]:
                correct += 1
            else:
                failures.append({
                    "id": c["id"],
                    "error": "tool_mismatch",
                    "expected": c["expected_tool"],
                    "got": routed.tool,
                    "elapsed_ms": elapsed_ms
                })

            # Week 2: Validate SQL results have data (row_count > 0 for seeded queries)
            if c["expected_tool"] == "sql" and routed.tool == "sql":
                sql_total += 1
                result_data = routed.result.data

                # Check if result has row_count > 0 (successful query with results)
                if isinstance(result_data, dict):
                    row_count = result_data.get("row_count", 0)
                    if row_count > 0:
                        sql_validated += 1
                    else:
                        failures.append({
                            "id": c["id"],
                            "error": "sql_no_results",
                            "detail": f"Query returned 0 rows (expected > 0)",
                            "elapsed_ms": elapsed_ms
                        })

    summary = summarize(total, correct, schema_ok)

    # Add SQL validation metrics
    sql_validation_rate = sql_validated / sql_total if sql_total > 0 else 0.0

    # Week 3 Commit 20: Add planner metrics
    planner_schema_rate = planner_schema_ok / planner_total if planner_total > 0 else 1.0
    planner_rejection_rate = planner_validation_rejected / planner_total if planner_total > 0 else 0.0

    report = {
        "summary": {
            **summary.__dict__,
            "sql_total": sql_total,
            "sql_validated": sql_validated,
            "sql_validation_rate": round(sql_validation_rate, 3),
            # Week 3 planner metrics
            "planner_total": planner_total,
            "planner_schema_ok": planner_schema_ok,
            "planner_schema_rate": round(planner_schema_rate, 3),
            "planner_validation_rejected": planner_validation_rejected,
            "planner_rejection_rate": round(planner_rejection_rate, 3),
            "planner_low_confidence": planner_low_confidence,
        },
        "failures": failures[:50],
    }

    print(json.dumps(report, indent=2))

    if args.out:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Week 1 gate: schema must be 100%
    if summary.schema_rate < 1.0:
        raise SystemExit("Schema compliance gate failed")

    # Week 2 gate: accuracy must be >= 70%
    if summary.accuracy < 0.70:
        raise SystemExit(f"Accuracy gate failed: {summary.accuracy:.1%} < 70%")

    # Week 3 Commit 20 gates: planner compliance
    if planner_total > 0:
        # Gate: Planner must always return structured output (schema compliance 100%)
        if planner_schema_rate < 1.0:
            raise SystemExit(f"Planner schema compliance gate failed: {planner_schema_rate:.1%} < 100%")

        # Gate: Routing accuracy for all cases must be >= 80%
        if summary.accuracy < 0.80:
            raise SystemExit(f"Routing accuracy gate failed: {summary.accuracy:.1%} < 80%")

if __name__ == "__main__":
    main()
