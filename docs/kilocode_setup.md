# Kilocode LLM Provider Setup

This guide explains how to configure and use the Kilocode LLM provider for natural language SQL queries.

## What is Kilocode?

Kilocode provides access to frontier AI models through an OpenRouter-compatible API. The Enterprise Tool Router integrates with Kilocode to convert natural language questions into safe, validated SQL queries.

## Setup

### 1. Get Your API Key

1. Sign up at [kilo.ai](https://kilo.ai)
2. Navigate to your profile/settings
3. Copy your API key (JWT token format)

### 2. Configure Environment Variable

Create a `.env` file in the project root (or add to your existing one):

```bash
# Kilocode API Configuration
KILOCODE_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...your_token_here

# Optional: Override default model
# KILOCODE_MODEL=google/gemini-2.5-flash-preview-05-20
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

The Kilocode provider uses the `requests` library which is now included in `requirements.txt`.

## Usage

### Automatic Initialization

The router automatically detects and initializes the Kilocode provider if `KILOCODE_API_KEY` is set:

```python
from enterprise_tool_router.router import ToolRouter

# Automatically uses KilocodeProvider if KILOCODE_API_KEY is set
router = ToolRouter()

# Now you can use natural language SQL queries
result = router.handle("show me revenue by region")
```

### Manual Initialization

You can also manually provide the LLM provider:

```python
from enterprise_tool_router.router import ToolRouter
from enterprise_tool_router.llm.providers import KilocodeProvider

# Create provider explicitly
provider = KilocodeProvider(
    api_key="eyJhbGci...",  # or reads from KILOCODE_API_KEY
    model="google/gemini-2.5-flash-preview-05-20"  # optional
)

# Pass to router
router = ToolRouter(llm_provider=provider)
```

## Natural Language SQL Examples

Once configured, you can ask questions in natural language:

```python
# Revenue by region
result = router.handle("show revenue by region from sales")

# Top performing products
result = router.handle("what are the top 10 products by revenue?")

# Job status summary
result = router.handle("count job runs by status")
```

The system will:
1. Convert your question to SQL using Kilocode
2. Validate the generated SQL for safety (read-only, allowlisted tables)
3. Execute the query and return results
4. Track token usage and cost

## Safety Features

All LLM-generated SQL queries go through the same 5-layer safety validation as raw SQL:

1. **SELECT-only**: Only SELECT statements allowed
2. **No semicolons**: Prevents SQL injection
3. **Keyword blocking**: Blocks DDL/DML operations (INSERT, UPDATE, DELETE, DROP, etc.)
4. **Table allowlist**: Only queries against approved tables (sales_fact, job_runs, audit_log)
5. **LIMIT enforcement**: Automatically adds LIMIT 200 if not specified

Additionally, queries with confidence scores below 0.7 are blocked and require clarification.

## Confidence Threshold

The router includes a confidence threshold to prevent ambiguous queries:

```python
from enterprise_tool_router.tools.sql import SqlTool
from enterprise_tool_router.llm.providers import KilocodeProvider

provider = KilocodeProvider()

# Set custom confidence threshold (default: 0.7)
sql_tool = SqlTool(
    llm_provider=provider,
    confidence_threshold=0.8  # Require 80% confidence
)
```

If a query's confidence is too low, you'll get a clarification message with the suggested SQL.

## Cost Tracking

The Kilocode provider tracks token usage and cost:

```python
result = router.handle("show revenue by region")

# Access cost information from audit logs
# Cost is tracked per request with correlation_id
```

Cost data is included in the response `usage` field and logged to the audit trail.

## Troubleshooting

### "Natural language queries require LLM provider" Error

This means the SqlTool was initialized without an LLM provider. Ensure:
- `KILOCODE_API_KEY` is set in your environment
- The `.env` file is loaded (use `python-dotenv` if needed)
- Or manually pass `llm_provider` to `ToolRouter()`

### "KILOCODE_API_KEY environment variable not set" Error

The API key is missing. Set it in your `.env` file or pass it directly:

```python
provider = KilocodeProvider(api_key="your_key_here")
```

### API Request Failures

Check:
- API key is valid and not expired
- Network connectivity to `kilocode.ai`
- API quota/credits (contact hi@kilo.ai for billing questions)

## Alternative Providers

The system also supports other LLM providers:

- **Anthropic (Claude)**: Set `ANTHROPIC_API_KEY`
- **OpenAI (GPT)**: Set `OPENAI_API_KEY`

See the provider classes in `src/enterprise_tool_router/llm/providers/` for details.

## References

- [Kilocode Documentation](https://kilo.ai/docs)
- [OpenRouter Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs)
- [Enterprise Tool Router README](../README.md)
