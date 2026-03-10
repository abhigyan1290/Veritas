Veritas — AI Cost Attribution & Change Detection
===============================================

## 1. Project Overview

Veritas is a developer-first platform that makes AI costs **transparent, attributable, and actionable**. It ties AI spend directly to **features**, **code versions**, and **deployments**, answering the question:

> “Which code change increased our AI costs?”

Initial focus is a Python SDK that instruments AI API calls (e.g. OpenAI) to emit structured cost events. These events later power change detection, CI checks, and a minimal dashboard that surfaces cost regressions per feature and commit.

This roadmap is written to make Veritas **pitchable to Y Combinator** and to support iterating in small, testable pieces.

## 2. YC Alignment

- **AI-native infra**: Veritas is core AI infrastructure, enabling teams to ship AI features while keeping costs under control—a clear fit with YC’s AI focus.
- **Big, urgent problem**: AI costs are growing fast and are currently treated as a billing problem, not an engineering problem. Veritas reframes this as **“cost regressions per feature/commit”**.
- **Clear wedge**: Start with **cost regression checks in CI + SDK**, then expand into full AI FinOps (alerts, optimization, governance).
- **Founder/workflow empathy**: Built for developers, integrated directly into code, with CLI and PR comments—used daily by engineers, not just finance.

## 3. High-Level Roadmap

We’ll build Veritas in phases, each with a **clear, demoable artifact** and **tight feedback loop**. Phases are ordered so that we can show something meaningful to YC quickly, then deepen the product.

### Phase 0 — Problem Validation & Design Partners

**Goal:** Confirm pain, refine positioning, and collect real usage patterns.

- Talk to 10–20 teams that use OpenAI/Anthropic heavily (chat, RAG, workflows).
- Validate:
  - How they monitor or think about AI costs today.
  - Who “owns” AI cost (eng vs. product vs. finance).
  - Whether “which code change increased our AI costs?” resonates.
- Collect:
  - Example code snippets of AI usage.
  - Existing metrics/logs they care about (tokens, latency, cost per feature).
- Recruit 3–5 **design partners** willing to:
  - Install a small Python package.
  - Run a script/test suite before & after changes.
  - Give feedback weekly.

**Output:** Clear problem statement, target user profile (e.g. eng leaders + senior ICs), and 3–5 design partners committed to trialing the SDK.

### Phase 1 — Local SDK MVP (Offline, Per-Developer)

**Goal:** Make it trivial for a single developer to see **cost per feature + commit** locally, without any backend.

Scope:

- **1.1 Core Python SDK**
  - `@track(feature="...")` decorator for sync/async functions.
  - Capture:
    - model name
    - tokens in/out (from provider response when available)
    - latency
    - status (ok/error)
    - feature
    - code version (git commit hash)
    - timestamp
  - Pluggable `Sink` interface:
    - `ConsoleSink` (JSON events to stdout).
    - `SQLiteSink` (local file, simple schema).

- **1.2 Pricing & Estimation**
  - Simple pricing table for key OpenAI models.
  - Graceful fallback when usage fields missing:
    - Mark events as `estimated=true` when approximate.

- **1.3 Developer Experience**
  - Easy installation: `pip install veritas-ai` (placeholder name).
  - Minimal configuration:
    - Auto-detect git commit hash.
    - Default sink: `ConsoleSink`, optional env var to enable `SQLiteSink`.
  - Sample repo:
    - Small Python script that calls OpenAI with `@track`.
    - `make run` prints a few tracked calls.

- **1.4 Local Inspection Tool**
  - CLI: `veritas events tail` to view recent events from SQLite/console logs.
  - Aggregation CLI: `veritas stats --feature chat_search --since 1h`.

**Success criteria for Phase 1:**

- Developers can integrate SDK in <15 minutes.
- They can answer: “What did my last script/test run cost, by feature?” using only local artifacts.

### Phase 2 — Minimal Change Detection Engine (Local / CLI)

**Goal:** Provide a **first useful answer** to “Which change increased costs?” for one developer, locally.

Scope:

- **2.1 Data Model for Comparisons**
  - Events stored with:
    - `feature`, `model`, `commit`, `cost_usd`, `tokens_in`, `tokens_out`, `latency_ms`, `status`, `timestamp`.
  - Define a comparison unit: e.g. N requests per (feature, model, commit).

- **2.2 CLI-Based Change Detection**
  - Command: `veritas diff --feature chat_search --from COMMIT_A --to COMMIT_B`.
  - Outputs:
    - avg cost per request (A vs. B)
    - avg tokens in/out (A vs. B)
    - delta + percent change
    - simple projected monthly increase (configurable volume).

- **2.3 Regression Heuristics**
  - Naive but explicit rules:
    - “Regression” if:
      - `avg_cost_per_request` increase >= X% AND
      - absolute delta >= \$Y and
      - at least N samples per side.
  - Make thresholds configurable.

**Success criteria for Phase 2:**

- On a demo project, running a script before and after a code change can show a clear diff (e.g. longer prompts or more expensive model) via CLI.
- Design partners can reproduce this on their own code.

### Phase 3 — Hosted Ingestion & Minimal Dashboard

**Goal:** Move from **per-developer** to **team-level visibility** with a lightweight web UI.

Scope:

- **3.1 Cloud Ingestion API**
  - `HttpSink` that batches events and sends them to a hosted ingestion endpoint.
  - Simple authentication (project API key).
  - Backend persists events (e.g. Postgres or similar).

- **3.2 Minimal Dashboard**
  - Authenticated web app with three views:
    - **Overview:**
      - Total AI spend (approx).
      - Top features by cost.
      - Recent regressions.
    - **Cost by Feature:**
      - Table: feature | cost per request | total cost | last 7/30 days.
    - **Cost Changes / Regression Feed:**
      - List of detected regressions:
        - Feature
        - Commit
        - Before vs. after cost per request
        - Projected monthly delta.

- **3.3 Onboarding & DX**
  - Simple signup → project → API key → copy-paste SDK config.
  - One demo tenant pre-populated for YC/demo usage.

**Success criteria for Phase 3:**

- A YC partner can sign in, see:
  - A real team’s sample data.
  - A clear regression story tied to commits.
- At least 2–3 design partners send events to the hosted backend.

### Phase 4 — CI / PR Integration (Core YC Wedge)

**Goal:** Make Veritas part of the **developer loop** by surfacing cost regressions where engineers already work: PRs and CI.

Scope:

- **4.1 CI Workflow**
  - GitHub Action (and/or generic CI script) that:
    - Runs a representative test suite / synthetic workload.
    - Pushes events to Veritas via SDK.
    - Calls a Veritas API/CLI to compare current run vs. baseline (e.g., last main commit).

- **4.2 PR Comments and Status Checks**
  - GitHub integration that posts on PRs:
    - “Cost report for this PR”:
      - Features touched.
      - Estimated change in cost per request.
      - Projected monthly delta at current traffic.
    - Optionally, mark checks as failing if regression passes a hard threshold.

- **4.3 Baseline Management**
  - Define how “baseline” is chosen:
    - Default: last successful main deploy.
    - Option to mark certain runs as golden baselines.

**Success criteria for Phase 4:**

- For at least one design partner, Veritas runs in CI and leaves visible comments/status on PRs that developers pay attention to.
- Demo: open PR → CI runs Veritas → PR comment shows cost impact.

### Phase 5 — Smarter Change Detection & Insights

**Goal:** Reduce noise, add value beyond raw deltas, and start moving toward “AI FinOps co-pilot”.

Scope:

- **5.1 Better Statistical Detection**
  - Move from fixed thresholds to simple statistical tests (e.g., comparing distributions of cost/request, tokens).
  - Visualizations to show variance and confidence.

- **5.2 Prompt/Model Optimization Hints**
  - Surface obvious low-hanging fruit:
    - “This feature could use gpt-4o-mini instead of gpt-4o with similar output length but 3x cheaper.”
    - “Prompt length increased 40% vs last baseline.”

- **5.3 Alerts & Notifications**
  - Basic alerting (email/Slack):
    - “Feature X cost per request increased > 50% week-over-week.”

**Success criteria for Phase 5:**

- Users report that alerts/findings are **useful and not noisy**.
- At least one customer uses Veritas insights to **substantially reduce AI costs** and is willing to share a story/quote.

### Phase 6 — Towards Full AI FinOps Platform

**Goal:** Expand the product surface while staying grounded in the original wedge.

Potential directions:

- Multi-language SDKs (Node, Go, etc.).
- Provider-agnostic support (OpenAI, Anthropic, local models).
- Budgeting/quotas and governance (per-team/feature limits).
- Org-wide analytics: cost per team, per product, per environment.

## 4. Milestones for YC Narrative

To be compelling to Y Combinator, we want progress that maps clearly to their mental model:

1. **Working product**:
   - SDK + local change detection working in real codebases (Phases 1–2).
2. **Real users**:
   - 3–5 design partners instrumented; at least 1 running CI/PR integration.
3. **Evidence of pull**:
   - Engineers ask for more languages/providers.
   - At least one story where Veritas caught an expensive regression before it hit production.
4. **Clear bigger vision**:
   - “From CI cost regressions to full AI FinOps platform for engineering teams.”

This roadmap is meant to be **iterative**: we can cut or reorder pieces based on what we learn, but each phase still produces something we can ship, demo, and learn from.

---

## 5. Development Setup

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest

# Verify import
python -c "import veritas; print(veritas.__version__)"
```

---

## 6. SDK Integration Guide

### Installation

```bash
pip install veritas   # or: pip install -e . for local dev
```

### Configuration

Set these in a `.env` file in your project root:

```bash
VERITAS_API_KEY=sk-vrt-your-key-here     # From Dashboard > Settings
VERITAS_API_URL=http://localhost:8000/api/v1/events
VERITAS_MOCK_COMMIT=my-feature-branch    # Optional: override git hash for testing
```

> **Important:** Use `load_dotenv(override=True)` in your app entrypoint so `.env` always wins over existing shell env vars.

---

### Anthropic Integration

```python
import anthropic
import veritas

# One-line swap — only change your client initialization:
client = veritas.Anthropic(
    anthropic.AsyncAnthropic(),
    feature_name="beach_recommendation"  # Groups calls in the dashboard
)

# Non-streaming — identical to regular anthropic usage:
response = await client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=1024,
    messages=[{"role": "user", "content": "..."}]
)

# Streaming — also identical, cost tracked when stream ends:
async for event in await client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=1024,
    messages=[{"role": "user", "content": "..."}],
    stream=True
):
    if event.type == "content_block_delta":
        print(event.delta.text, end="")
```

---

### OpenAI Integration

```python
import openai
import veritas

# One-line swap:
client = veritas.OpenAI(
    openai.AsyncOpenAI(),
    feature_name="document_summary"
)

# Non-streaming:
response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "..."}]
)

# Streaming — veritas auto-injects stream_options for usage capture:
async for chunk in await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "..."}],
    stream=True
):
    print(chunk.choices[0].delta.content or "", end="")
```

---

### Data Flow — How Tokens Are Captured

| Mode | Provider | Token source | Event fires |
|---|---|---|---|
| Non-streaming sync | Anthropic | `response.usage.input_tokens` / `output_tokens` | After `create()` returns |
| Non-streaming async | Anthropic | `response.usage.input_tokens` / `output_tokens` | After `await create()` |
| Streaming sync | Anthropic | `message_start` event → input; `message_delta` event → output | When stream iterator exhausted |
| Streaming async | Anthropic | Same, via `async for` | When async iterator exhausted |
| Non-streaming sync | OpenAI | `response.usage.prompt_tokens` / `completion_tokens` | After `create()` returns |
| Non-streaming async | OpenAI | `response.usage.prompt_tokens` / `completion_tokens` | After `await create()` |
| Streaming sync | OpenAI | Final chunk (auto-injected `stream_options`) `prompt_tokens` / `completion_tokens` | When stream iterator exhausted |
| Streaming async | OpenAI | Same, via `async for` | When async iterator exhausted |

> Veritas auto-injects `stream_options={"include_usage": True}` for OpenAI streaming calls. The caller's code is unchanged.

---

### Pricing Reference (USD per 1M tokens)

#### Anthropic Claude

| Model | Input | Output | Cache Write | Cache Read |
|---|---|---|---|---|
| claude-opus-4 | $5.00 | $25.00 | $6.25 | $0.50 |
| claude-sonnet-4 | $3.00 | $15.00 | $3.75 | $0.30 |
| claude-haiku-4 | $1.00 | $5.00 | $1.25 | $0.10 |
| claude-3-5-sonnet | $3.00 | $15.00 | $3.75 | $0.30 |
| claude-3-5-haiku | $0.80 | $4.00 | $1.00 | $0.08 |
| claude-3-opus | $15.00 | $75.00 | $18.75 | $1.50 |
| claude-3-haiku | $0.25 | $1.25 | $0.30 | $0.03 |

#### OpenAI

| Model | Input | Output | Cached Input |
|---|---|---|---|
| o1 | $15.00 | $60.00 | $7.50 |
| o1-mini | $3.00 | $12.00 | $1.50 |
| o3-mini | $1.10 | $4.40 | $0.55 |
| gpt-4o | $2.50 | $10.00 | $1.25 |
| gpt-4o-mini | $0.15 | $0.60 | $0.075 |
| gpt-4-turbo | $10.00 | $30.00 | — |
| gpt-4 | $30.00 | $60.00 | — |
| gpt-3.5-turbo | $0.50 | $1.50 | — |

Unknown models fall back to `gpt-4o-mini` pricing and are marked `estimated=true` in the dashboard.
