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
