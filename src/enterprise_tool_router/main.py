from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

from .logging import setup_logging, correlation_id_middleware
from .schemas import QueryRequest, QueryResponse
from .router import ToolRouter
from .audit import audit_context

setup_logging()
app = FastAPI(title="Enterprise Tool Router", version="0.1.0")
app.middleware("http")(correlation_id_middleware)

router = ToolRouter()

REQS = Counter("router_requests_total", "Total requests", ["tool"])
LAT = Histogram("router_request_duration_ms", "Request duration in ms")
# Week 4 Commit 26: Token and cost metrics
TOKENS_IN = Counter("router_tokens_input_total", "Total input tokens consumed")
TOKENS_OUT = Counter("router_tokens_output_total", "Total output tokens generated")
COST = Counter("router_cost_usd_total", "Total estimated cost in USD")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, request: Request):
    # Get correlation ID from middleware
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    user_id = getattr(req, "user_id", None)

    # Audit the query operation
    with audit_context(
        correlation_id=correlation_id,
        tool="router",  # Will be updated to actual tool after routing
        action="query",
        input_data={"query": req.query, "user_id": user_id},
        user_id=user_id
    ) as audit_ctx:
        # Route and execute the query with correlation ID propagation
        # Week 4 Commit 27: Pass bypass_cache flag
        routed = router.handle(req.query, correlation_id=correlation_id, user_id=user_id, bypass_cache=req.bypass_cache)
        REQS.labels(tool=routed.tool).inc()
        LAT.observe(routed.elapsed_ms)
        # Week 4 Commit 26: Track token usage and cost
        if routed.tokens_input > 0:
            TOKENS_IN.inc(routed.tokens_input)
        if routed.tokens_output > 0:
            TOKENS_OUT.inc(routed.tokens_output)
        if routed.cost_usd > 0:
            COST.inc(routed.cost_usd)

        # Prepare response with correlation_id as trace_id for end-to-end tracing
        # Week 4 Commit 26: Include actual cost from LLM usage
        response = QueryResponse(
            tool_used=routed.tool,
            confidence=routed.confidence,
            result=routed.result.data,
            trace_id=correlation_id,  # Use correlation_id for distributed tracing
            cost_usd=routed.cost_usd,
            notes=routed.result.notes or None,
        )

        # Set audit output (marks operation as successful)
        # Week 4 Commit 26: Include token usage and cost in audit log
        audit_ctx.set_output(
            {
                "tool": routed.tool,
                "confidence": routed.confidence,
                "notes": routed.result.notes,
                "row_count": routed.result.data.get("row_count") if isinstance(routed.result.data, dict) else None
            },
            tokens_input=routed.tokens_input,
            tokens_output=routed.tokens_output,
            cost_usd=routed.cost_usd
        )

        return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("enterprise_tool_router.main:app", host="127.0.0.1", port=8000, reload=True)

