# OpenRouter LLM Provider Setup

This guide explains how to configure and use the OpenRouter LLM provider for **natural language to SQL conversion**.

## What is OpenRouter?

OpenRouter provides unified access to 200+ AI models (Claude, GPT-4, Gemini, Llama, and more) through a single API. The Enterprise Tool Router uses OpenRouter to **convert natural language questions into safe, validated SQL queries using LLMs**.

## How It Works

```
User Question: "Show me revenue by region"
        ↓
OpenRouter LLM (e.g., aurora-alpha)
        ↓
Generated SQL: "SELECT region, SUM(revenue) FROM sales_fact GROUP BY region LIMIT 100"
        ↓
5-Layer Safety Validation
        ↓
Execute against PostgreSQL
        ↓
Return results
```

## Setup

### 1. Get Your API Key

1. Sign up at [openrouter.ai](https://openrouter.ai)
2. Navigate to your [API Keys](https://openrouter.ai/keys) page
3. Create a new API key
4. Copy the key (format: `sk-or-v1-...`)

### 2. Configure Environment Variable

Create a `.env` file in the project root (or add to your existing one):

```bash
# OpenRouter Configuration
OPENROUTER_API_KEY=sk-or-v1-your_key_here
OPENROUTER_MODEL=openrouter/aurora-alpha  # Free tier, excellent performance

# Database Configuration (required)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=enterprise_tool_router
DB_USER=etr_user
DB_PASSWORD=your_password_here
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

The OpenRouter provider uses the `requests` library which is included in `requirements.txt`.

## Usage

### Automatic Initialization

The router automatically detects and initializes the OpenRouter provider if `OPENROUTER_API_KEY` is set:

```python
from enterprise_tool_router.router import ToolRouter

# Automatically uses OpenRouterProvider if OPENROUTER_API_KEY is set
router = ToolRouter()

# Now you can use natural language SQL queries
result = router.handle("show me revenue by region")
```

### Manual Initialization

You can also manually provide the LLM provider:

```python
from enterprise_tool_router.router import ToolRouter
from enterprise_tool_router.llm.providers import OpenRouterProvider

# Create provider explicitly
provider = OpenRouterProvider(
    api_key="sk-or-v1-...",  # or reads from OPENROUTER_API_KEY
    model="openrouter/aurora-alpha"  # or other model
)

# Pass to router
router = ToolRouter(llm_provider=provider)
```

## Natural Language SQL Examples

Once configured, you can ask questions in natural language and the LLM will convert them to SQL:

```python
# Revenue by region
result = router.handle("show revenue by region from sales")
# LLM generates: SELECT region, SUM(revenue) FROM sales_fact GROUP BY region LIMIT 100

# Top performing products
result = router.handle("what are the top 10 products by revenue?")
# LLM generates: SELECT product, SUM(revenue) FROM sales_fact GROUP BY product ORDER BY SUM(revenue) DESC LIMIT 10

# Job status summary
result = router.handle("count job runs by status")
# LLM generates: SELECT status, COUNT(*) FROM job_runs GROUP BY status LIMIT 100
```

The system will:
1. **Convert** your question to SQL using OpenRouter LLM
2. **Validate** the generated SQL for safety (read-only, allowlisted tables)
3. **Execute** the query and return results
4. **Track** token usage and cost

## Available Models

OpenRouter provides access to 200+ models. Popular choices for SQL generation:

### Free Tier (Recommended for Development)
- `openrouter/aurora-alpha` - Fast, free, excellent for SQL generation ✅ **Currently configured**
- `google/gemini-2.0-flash-thinking-exp:free` - Google's latest thinking model
- `meta-llama/llama-3.2-1b-instruct:free` - Fast, lightweight

### Paid Tier (Better Performance)
- `anthropic/claude-3.5-sonnet` - Excellent reasoning, high quality SQL
- `openai/gpt-4o` - Strong performance, widely used
- `google/gemini-2.5-flash-preview-05-20` - Fast and capable

See the full list at [openrouter.ai/models](https://openrouter.ai/models)

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
from enterprise_tool_router.llm.providers import OpenRouterProvider

provider = OpenRouterProvider()

# Set custom confidence threshold (default: 0.7)
sql_tool = SqlTool(
    llm_provider=provider,
    confidence_threshold=0.8  # Require 80% confidence
)
```

If a query's confidence is too low, you'll get a clarification message with the suggested SQL.

## Cost Tracking

The OpenRouter provider tracks token usage and cost:

```python
result = router.handle("show revenue by region")

# Access cost information from audit logs
# Cost is tracked per request with correlation_id
```

Cost data is included in the response and logged to the audit trail.

### Cost Estimates

- **aurora-alpha**: Free (recommended for development)
- **Claude 3.5 Sonnet**: ~$3.00/MTok input, ~$15.00/MTok output
- **GPT-4o**: ~$2.50/MTok input, ~$10.00/MTok output

A typical SQL generation query uses ~150-200 tokens total (< $0.01 for paid models).

## Troubleshooting

### "Natural language queries require LLM provider" Error

This means the SqlTool was initialized without an LLM provider. Ensure:
- `OPENROUTER_API_KEY` is set in your environment
- The `.env` file is loaded (use `python-dotenv` if needed)
- Or manually pass `llm_provider` to `ToolRouter()`

### "OPENROUTER_API_KEY environment variable not set" Error

The API key is missing. Set it in your `.env` file or pass it directly:

```python
provider = OpenRouterProvider(api_key="sk-or-v1-your_key_here")
```

### API Request Failures

Check:
- API key is valid and not expired
- Network connectivity to `openrouter.ai`
- API quota/credits (check your [OpenRouter dashboard](https://openrouter.ai/account))
- Model availability (some models have rate limits)

### "Generated SQL failed safety validation" Error

This is **expected behavior** - the LLM sometimes generates SQL that violates safety rules. Examples:

- Query contains semicolons (SQL injection risk)
- Query uses blocked keywords (DROP, DELETE, etc.)
- Query accesses non-allowlisted tables
- Query missing LIMIT clause

The system will reject these queries and return an error. This is the **safety validation working correctly**!

## Alternative Providers

The system also supports other LLM providers with the same interface:

- **Anthropic (Claude)**: Set `ANTHROPIC_API_KEY`
- **OpenAI (GPT)**: Set `OPENAI_API_KEY`

See the provider classes in `src/enterprise_tool_router/llm/providers/` for details.

## Performance Tips

1. **Use free models for development**: aurora-alpha is fast and free
2. **Monitor token usage**: Enable audit logging to track costs
3. **Cache common queries**: Consider caching LLM responses for repeated questions
4. **Use confidence thresholds**: Reject low-confidence queries early to save tokens

## Example: Full Integration

```python
import os
from enterprise_tool_router.router import ToolRouter

# Set up environment
os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-..."
os.environ["OPENROUTER_MODEL"] = "openrouter/aurora-alpha"

# Create router (auto-detects OpenRouter)
router = ToolRouter()

# Ask a natural language question
result = router.handle("What were the top 3 regions by revenue?")

# The LLM converts this to SQL:
# SELECT region, SUM(revenue) AS total_revenue
# FROM sales_fact
# GROUP BY region
# ORDER BY total_revenue DESC
# LIMIT 3

# Print results
print(f"Tool: {result.tool}")
print(f"Confidence: {result.confidence}")
print(f"Results: {result.result.data}")
```

## References

- [OpenRouter Documentation](https://openrouter.ai/docs)
- [OpenRouter Models](https://openrouter.ai/models)
- [OpenRouter Pricing](https://openrouter.ai/docs/pricing)
- [Enterprise Tool Router README](../README.md)
