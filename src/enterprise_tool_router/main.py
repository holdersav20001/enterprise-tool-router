from fastapi import FastAPI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

from .logging import setup_logging, correlation_id_middleware
from .schemas import QueryRequest, QueryResponse
from .router import ToolRouter

setup_logging()
app = FastAPI(title="Enterprise Tool Router", version="0.1.0")
app.middleware("http")(correlation_id_middleware)

router = ToolRouter()

REQS = Counter("router_requests_total", "Total requests", ["tool"])
LAT = Histogram("router_request_duration_ms", "Request duration in ms")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    routed = router.handle(req.query)
    REQS.labels(tool=routed.tool).inc()
    LAT.observe(routed.elapsed_ms)
    trace_id = getattr(req, "user_id", None) or "local"
    return QueryResponse(
        tool_used=routed.tool,
        confidence=routed.confidence,
        result=routed.result.data,
        trace_id=trace_id,
        cost_usd=0.0,
        notes=routed.result.notes or None,
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("enterprise_tool_router.main:app", host="127.0.0.1", port=8000, reload=True)

