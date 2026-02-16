from enterprise_tool_router.router import ToolRouter

def test_router_instantiates():
    r = ToolRouter()
    assert r is not None

def test_routing_sql():
    r = ToolRouter()
    tool, conf = r.route("Show revenue by region")
    assert tool == "sql"
    assert conf > 0.5

def test_routing_vector():
    r = ToolRouter()
    tool, conf = r.route("Show me the runbook for CDC failures")
    assert tool == "vector"
    assert conf > 0.5

def test_routing_rest():
    r = ToolRouter()
    tool, conf = r.route("Call API endpoint status for service X")
    assert tool == "rest"
    assert conf > 0.5

