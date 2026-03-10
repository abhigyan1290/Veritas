"""Generate random sample cost events for schema inspection and testing.

Run from project root:
    python scripts/generate_sample_data.py

Creates:
- sample_events.db (SQLite with random events)
- schema_and_sample.txt (printable schema + sample rows)
"""

import random
import sqlite3
import sys
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veritas import CostEvent, SQLiteSink
from veritas.sinks import EVENTS_SCHEMA

FEATURES = ["chat_search", "doc_summary", "code_review", "support_bot", "rag_query"]
MODELS = ["claude-3-5-sonnet", "claude-3-haiku", "claude-opus-4"]
STATUSES = ["ok", "ok", "ok", "error"]  # mostly ok


def random_event(seed: int) -> CostEvent:
    """Generate one random cost event."""
    r = random.Random(seed)
    tokens_in = r.randint(50, 2000)
    tokens_out = r.randint(20, 500)
    cost_usd = round(r.uniform(0.0001, 0.05), 6)
    return CostEvent(
        feature=r.choice(FEATURES),
        model=r.choice(MODELS),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=round(r.uniform(100, 3000), 1),
        cost_usd=cost_usd,
        code_version=r.choice(["a81cd29", "b2ef3a1", None, "c9d4e5f"]),
        timestamp=f"2026-03-0{r.randint(1,6)}T{r.randint(10,23):02d}:{r.randint(0,59):02d}:{r.randint(0,59):02d}Z",
        status=r.choice(STATUSES),
        estimated=r.random() < 0.2,
    )


def main():
    out_dir = Path(__file__).parent.parent
    db_path = out_dir / "sample_events.db"
    txt_path = out_dir / "schema_and_sample.txt"

    # Generate 20 random events
    events = [random_event(i) for i in range(20)]

    # Write to SQLite
    sink = SQLiteSink(db_path)
    for e in events:
        sink.emit(e)
    sink.close()

    # Build printable output
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, feature, model, tokens_in, tokens_out, latency_ms, "
        "cost_usd, code_version, timestamp, status, estimated FROM events LIMIT 10"
    ).fetchall()
    conn.close()

    lines = [
        "=" * 60,
        "VERITAS — EVENTS TABLE SCHEMA",
        "=" * 60,
        "",
        EVENTS_SCHEMA.strip(),
        "",
        "=" * 60,
        "SAMPLE ROWS (first 10 of 20)",
        "=" * 60,
    ]

    if rows:
        # Column widths for readable output
        widths = {"id": 4, "feature": 14, "model": 18, "tokens_in": 10, "tokens_out": 11,
                  "latency_ms": 10, "cost_usd": 10, "code_version": 12, "timestamp": 22,
                  "status": 8, "estimated": 4}
        headers = list(rows[0].keys())
        w = [widths.get(h, 12) for h in headers]
        lines.append(" | ".join(str(h).ljust(w[i]) for i, h in enumerate(headers)))
        lines.append("-" * (sum(w) + 3 * (len(headers) - 1)))

        for row in rows:
            vals = []
            for i, h in enumerate(headers):
                v = str(row[h]) if row[h] is not None else "NULL"
                vals.append(v[: w[i]].ljust(w[i]) if len(v) > w[i] else v.ljust(w[i]))
            lines.append(" | ".join(vals))

    lines.extend(["", "=" * 60])

    content = "\n".join(lines)
    txt_path.write_text(content, encoding="utf-8")

    print(f"Created {db_path}")
    print(f"Printed schema + sample to {txt_path}")
    print()
    print(content)


if __name__ == "__main__":
    main()
