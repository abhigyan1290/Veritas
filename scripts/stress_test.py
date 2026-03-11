"""
Veritas Ingest Stress Test
==========================
Sends synthetic CostEvent payloads directly to the live Railway endpoint.
No real LLM calls are made — zero token cost.

Tests:
  - Burst: 50 concurrent requests
  - Sustained: 200 sequential requests
  - Concurrency: 20 workers × 10 requests each
  - Health: /health endpoint availability

Usage:
  python scripts/stress_test.py [API_KEY]
"""
import sys
import time
import statistics
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

# ─── Config ─────────────────────────────────────────────────────────────────
BASE_URL   = "https://web-production-82424.up.railway.app"
# Use demo project key (always exists — seeded by ensure_demo_tenant on boot)
API_KEY    = sys.argv[1] if len(sys.argv) > 1 else "sk-vrt-demo"
INGEST_URL = f"{BASE_URL}/api/v1/events"
HEALTH_URL = f"{BASE_URL}/health"
HEADERS    = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

def make_payload(feature: str = "stress_test", commit: str = "stress-abc123") -> dict:
    """Synthetic CostEvent — no real tokens used."""
    return {
        "feature": feature,
        "model": "claude-3-haiku-20240307",
        "tokens_in": 10,
        "tokens_out": 5,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "latency_ms": 120.0,
        "cost_usd": 0.000002,
        "code_version": commit,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok",
        "estimated": False
    }

def send_one(session: requests.Session, feature: str = "stress_test") -> dict:
    start = time.perf_counter()
    try:
        r = session.post(INGEST_URL, json=make_payload(feature), timeout=10)
        elapsed = (time.perf_counter() - start) * 1000
        return {"ok": r.status_code == 200, "status": r.status_code, "ms": elapsed}
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return {"ok": False, "status": -1, "ms": elapsed, "error": str(e)}

def print_stats(label: str, results: list[dict]):
    total    = len(results)
    ok       = sum(1 for r in results if r["ok"])
    failed   = total - ok
    latencies = [r["ms"] for r in results]
    latencies.sort()

    p50  = statistics.median(latencies)
    p95  = latencies[int(len(latencies) * 0.95)]
    p99  = latencies[int(len(latencies) * 0.99)] if len(latencies) >= 100 else latencies[-1]
    avg  = statistics.mean(latencies)
    err_codes = {}
    for r in results:
        if not r["ok"]:
            code = r.get("status", "?")
            err_codes[code] = err_codes.get(code, 0) + 1

    print(f"\n{'='*55}")
    print(f"  {label}")
    print(f"{'='*55}")
    print(f"  Total requests : {total}")
    print(f"  Succeeded      : {ok}  ({ok/total*100:.1f}%)")
    print(f"  Failed         : {failed}")
    if err_codes:
        print(f"  Error codes    : {err_codes}")
    print(f"  Latency (ms)   :")
    print(f"    avg  = {avg:.1f}")
    print(f"    p50  = {p50:.1f}")
    print(f"    p95  = {p95:.1f}")
    print(f"    p99  = {p99:.1f}")
    print(f"    min  = {min(latencies):.1f}")
    print(f"    max  = {max(latencies):.1f}")



# ─── Phase 0: Health Check ───────────────────────────────────────────────────
print(f"\nVeritas Stress Test -> {BASE_URL}")
print(f"API Key : {API_KEY[:12]}...")

print("\n[0] Health check...", end=" ", flush=True)
try:
    r = requests.get(HEALTH_URL, timeout=10)
    if r.status_code == 200:
        print("OK")
    else:
        print(f"FAIL HTTP {r.status_code} -- {r.text}")
        sys.exit(1)
except Exception as e:
    print(f"FAIL Connection failed: {e}")
    sys.exit(1)

session = requests.Session()
session.headers.update(HEADERS)

# ─── Phase 1: Single Request Baseline ────────────────────────────────────────
print("\n[1] Single request baseline...", end=" ", flush=True)
r1 = send_one(session)
print(f"{'✓' if r1['ok'] else '✗'} {r1['status']} ({r1['ms']:.0f}ms)")
if not r1["ok"]:
    print("    ERROR: Ingest endpoint is rejecting requests. Check API key or deployment.")
    sys.exit(1)

# ─── Phase 2: Burst — 50 concurrent ──────────────────────────────────────────
print("\n[2] Burst: 50 concurrent requests...", end=" ", flush=True)
t_start = time.perf_counter()
with ThreadPoolExecutor(max_workers=50) as pool:
    futures = [pool.submit(send_one, session, "burst_test") for _ in range(50)]
    burst_results = [f.result() for f in as_completed(futures)]
burst_duration = time.perf_counter() - t_start
print(f"done ({burst_duration:.1f}s wall time)")
print_stats("BURST — 50 concurrent requests", burst_results)

# ─── Phase 3: Sustained — 200 sequential ─────────────────────────────────────
print(f"\n[3] Sustained: 200 sequential requests...", end=" ", flush=True)
sustained_results = []
t_start = time.perf_counter()
for i in range(200):
    sustained_results.append(send_one(session, f"sustained_{i % 5}"))
wall = time.perf_counter() - t_start
throughput = 200 / wall
print(f"done ({wall:.1f}s — {throughput:.1f} req/s)")
print_stats("SUSTAINED — 200 sequential requests", sustained_results)

# ─── Phase 4: Concurrent Workers — 20 × 25 ───────────────────────────────────
print(f"\n[4] Concurrent workers: 20 workers × 25 requests each (500 total)...", end=" ", flush=True)
t_start = time.perf_counter()

def worker_batch(worker_id: int):
    s = requests.Session()
    s.headers.update(HEADERS)
    return [send_one(s, f"worker_{worker_id}") for _ in range(25)]

with ThreadPoolExecutor(max_workers=20) as pool:
    batches = list(pool.map(worker_batch, range(20)))
concurrent_results = [r for batch in batches for r in batch]
wall = time.perf_counter() - t_start
print(f"done ({wall:.1f}s wall time)")
print_stats("CONCURRENT — 20 workers × 25 req (500 total)", concurrent_results)

# ─── Summary ──────────────────────────────────────────────────────────────────
all_results = burst_results + sustained_results + concurrent_results
total = len(all_results)
ok = sum(1 for r in all_results if r["ok"])
print(f"\n{'='*55}")
print(f"  OVERALL: {ok}/{total} succeeded ({ok/total*100:.1f}%)")
print(f"{'='*55}\n")
