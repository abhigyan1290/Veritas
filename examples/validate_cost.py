"""Cost validation run: varied prompts (small/medium/large), full call log, compare to billing.

Run from project root:
    python examples/validate_cost.py

- Runs several scenarios: small input/output, medium, and larger prompts (varying tokens).
- One intentional failure (invalid model) → recorded with cost_usd=0, status=error.
- All events go to SQLite (validation_events.db) and a timestamped log file.
- Prints a table of every call and total cost for comparison with Anthropic billing.
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_env():
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)


_load_env()

from veritas import track
from veritas.sinks import SQLiteSink

try:
    import anthropic
except ImportError:
    print('Run: pip install -e ".[examples]"')
    sys.exit(1)


def get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("Set ANTHROPIC_API_KEY in .env or environment.")
        sys.exit(1)
    return key


# DB and log paths (in project root)
DB_PATH = ROOT / "validation_events.db"
LOG_DIR = ROOT / "validation_logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_PATH = LOG_DIR / f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"

# Models
MODEL_OK = "claude-sonnet-4-20250514"
MODEL_INVALID = "claude-invalid-model-for-test"  # Intentional: triggers API error, cost 0

# Scenarios: varied prompt sizes and max_tokens to exercise small, medium, and large in/out
SCENARIOS = [
    {
        "name": "tiny",
        "prompt": "Reply with exactly: OK",
        "max_tokens": 10,
    },
    {
        "name": "small_qa",
        "prompt": "What is 2+2? Reply with one number only.",
        "max_tokens": 20,
    },
    {
        "name": "medium_summary",
        "prompt": (
            "Here is a short paragraph. "
            "The quick brown fox jumps over the lazy dog. "
            "Python is a programming language. "
            "Summarize this in one sentence."
        ),
        "max_tokens": 80,
    },
    {
        "name": "medium_bullets",
        "prompt": (
            "Topic: benefits of version control. "
            "List exactly three short bullet points."
        ),
        "max_tokens": 120,
    },
    {
        "name": "large_input",
        "prompt": (
            "Read this text and summarize in two sentences. "
            "Artificial intelligence has transformed how we build software. "
            "Large language models can assist with code, documentation, and design. "
            "Teams use AI to automate repetitive tasks and explore ideas faster. "
            "Responsible use requires testing, review, and clear boundaries. "
            "The future of development will blend human judgment with AI tools."
        ),
        "max_tokens": 150,
    },
    {
        "name": "larger_output",
        "prompt": "Name five programming languages. For each, write one short sentence about it.",
        "max_tokens": 200,
    },
    # Different model (cheaper tier) — if this model 404s, edit or remove it
    {
        "name": "different_model_haiku",
        "prompt": "Say hello in one word.",
        "max_tokens": 10,
        "model": "claude-haiku-4-20250514",
    },
]


def run_validation():
    api_key = get_api_key()
    sink = SQLiteSink(DB_PATH)

    @track(feature="validate_cost", sink=sink)
    def call_claude(prompt: str, model: str, max_tokens: int = 100):
        client = anthropic.Anthropic(api_key=api_key)
        return client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

    lines = []
    lines.append("=" * 70)
    lines.append("VERITAS COST VALIDATION RUN")
    lines.append(f"Started at {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"DB: {DB_PATH}")
    lines.append("=" * 70)

    # ---- Successful calls: varied scenarios (small / medium / large) ----
    for i, scenario in enumerate(SCENARIOS):
        name = scenario["name"]
        prompt = scenario["prompt"]
        max_tokens = scenario.get("max_tokens", 100)
        model = scenario.get("model", MODEL_OK)
        try:
            result = call_claude(prompt, model, max_tokens)
            lines.append(
                f"  [{i + 1}] {name}: ok, tokens in={result.usage.input_tokens} out={result.usage.output_tokens} "
                f"(max_tokens={max_tokens})"
            )
        except Exception as e:
            lines.append(f"  [{i + 1}] {name}: unexpected error: {e}")
    lines.append("")

    # ---- One intentional failure: invalid model -> no API charge, we record cost 0 ----
    lines.append("  Intentional failure (invalid model) — should appear as cost_usd=0, status=error")
    try:
        call_claude("no input", MODEL_INVALID)
    except Exception as e:
        lines.append(f"  (Expected) Error: {type(e).__name__}: {e}")
    lines.append("")

    sink.close()

    # ---- Query DB: full call log and totals ----
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, feature, model, tokens_in, tokens_out, latency_ms, cost_usd, status, timestamp "
        "FROM events ORDER BY id"
    ).fetchall()
    total_cost = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM events").fetchone()[0]
    conn.close()

    # Table header
    col_w = {"id": 4, "feature": 14, "model": 22, "tokens_in": 10, "tokens_out": 11,
             "latency_ms": 10, "cost_usd": 10, "status": 8, "timestamp": 22}
    headers = ["id", "feature", "model", "tokens_in", "tokens_out", "latency_ms", "cost_usd", "status", "timestamp"]
    lines.append("CALL LOG (all events)")
    lines.append("-" * 70)
    lines.append(" | ".join(h.ljust(col_w.get(h, 12)) for h in headers))
    lines.append("-" * 70)

    for row in rows:
        vals = []
        for h in headers:
            v = row[h]
            if v is None:
                v = "NULL"
            else:
                v = str(v)
            w = col_w.get(h, 12)
            vals.append(v[:w].ljust(w) if len(v) > w else v.ljust(w))
        lines.append(" | ".join(vals))

    lines.append("-" * 70)
    lines.append(f"Total cost (Veritas): ${total_cost:.6f}")
    lines.append("")
    lines.append("Compare this total to your Anthropic usage/billing for this time window.")
    lines.append("Failed calls (status=error) have cost_usd=0 and are not charged by the API.")
    lines.append("=" * 70)

    text = "\n".join(lines)
    LOG_PATH.write_text(text, encoding="utf-8")

    # Print to stdout
    print(text)
    print(f"\nLog saved to: {LOG_PATH}")

    # Sanity: last event (failure) should have cost 0
    if rows:
        last = rows[-1]
        if last["status"] == "error" and float(last["cost_usd"]) == 0.0:
            print("[OK] False call (invalid model) correctly recorded with cost_usd=0.")
        elif last["status"] == "error":
            print(f"[WARN] Last event is error but cost_usd={last['cost_usd']} (expected 0).")


if __name__ == "__main__":
    run_validation()
