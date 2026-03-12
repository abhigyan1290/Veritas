# Veritas

**AI cost observability for developers.** Track token usage, costs, and latency across every LLM call — automatically. Spot cost regressions before they hit production.

```bash
pip install veritas-sdk[anthropic]
# or
pip install veritas-sdk[openai]
# or
pip install veritas-sdk[all]
```

---

## What it does

Veritas wraps your existing Anthropic or OpenAI client with a transparent proxy. Every API call is tracked silently in the background — your application code stays identical.

For every call, Veritas captures:

| Field | Description |
|-------|-------------|
| `feature` | The feature name you assign |
| `model` | Model used (e.g. `claude-3-haiku`, `gpt-4o-mini`) |
| `tokens_in / tokens_out` | Input and output token counts |
| `cost_usd` | Computed cost based on current pricing |
| `latency_ms` | End-to-end request time |
| `code_version` | Current git commit hash (auto-detected) |

Events are sent to a Veritas dashboard where you can track spend over time, break costs down by feature, and compare costs between code versions.

---

## Quickstart

### 1. Configure

```python
import veritas

veritas.init(
    api_key="sk-vrt-your-key-here",
    endpoint="https://your-veritas-server.com/api/v1/events",
)
```

Alternatively, use environment variables — Veritas auto-configures on import:

```bash
VERITAS_API_KEY=sk-vrt-your-key-here
VERITAS_API_URL=https://your-veritas-server.com/api/v1/events
```

### 2. Wrap your client

**Anthropic:**

```python
import anthropic
import veritas

veritas.init(api_key="sk-vrt-...", endpoint="https://your-server.com/api/v1/events")

client = veritas.Anthropic(
    anthropic.Anthropic(),
    feature_name="chat_search",   # group calls by feature in the dashboard
)

response = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=256,
    messages=[{"role": "user", "content": "Hello!"}],
)
# ^ tracked automatically — response is unchanged
```

**OpenAI:**

```python
import openai
import veritas

veritas.init(api_key="sk-vrt-...", endpoint="https://your-server.com/api/v1/events")

client = veritas.OpenAI(
    openai.OpenAI(),
    feature_name="summarizer",
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

Streaming works too — just pass `stream=True` as normal.

### 3. Use the `@track` decorator (alternative)

```python
from veritas import track

@track(feature="document_summary")
def summarize(text: str):
    return anthropic_client.messages.create(...)   # any call that returns usage data
```

---

## Safety guarantees

- **Never crashes your app** — all tracking is fire-and-forget; exceptions are swallowed silently
- **No prompt data transmitted** — only metadata (tokens, cost, latency, model, commit hash)
- **Async-safe** — uses `asyncio.to_thread` in async contexts so the event loop is never blocked
- **Zero-config git integration** — commit hash is auto-detected via `git rev-parse`

---

## Requirements

- Python 3.9+
- `requests` (for HTTP sink)
- `anthropic>=0.39` (if using `veritas-sdk[anthropic]`)
- `openai>=1.0.0` (if using `veritas-sdk[openai]`)

---

## Links

- [GitHub](https://github.com/abhigyan1290/veritas-ai)
- [Dashboard](https://web-production-82424.up.railway.app) — request access at [abhitandon449@gmail.com](mailto:abhitandon449@gmail.com)

