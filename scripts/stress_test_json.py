"""Collect stress test results and write to JSON."""
import sys
import time
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

BASE_URL   = "https://web-production-82424.up.railway.app"
API_KEY    = "sk-vrt-demo"
INGEST_URL = f"{BASE_URL}/api/v1/events"
HEALTH_URL = f"{BASE_URL}/health"
HEADERS    = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

def make_payload(feature="stress_test"):
    return {
        "feature": feature,
        "model": "claude-3-haiku-20240307",
        "tokens_in": 10, "tokens_out": 5,
        "cache_creation_tokens": 0, "cache_read_tokens": 0,
        "latency_ms": 120.0, "cost_usd": 0.000002,
        "code_version": "stress-abc123",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok", "estimated": False
    }

def send_one(session, feature="stress_test"):
    start = time.perf_counter()
    try:
        r = session.post(INGEST_URL, json=make_payload(feature), timeout=10)
        ms = (time.perf_counter() - start) * 1000
        return {"ok": r.status_code == 200, "status": r.status_code, "ms": ms}
    except Exception as e:
        ms = (time.perf_counter() - start) * 1000
        return {"ok": False, "status": -1, "ms": ms, "error": str(e)}

def stats(results):
    lats = sorted(r["ms"] for r in results)
    ok = sum(1 for r in results if r["ok"])
    n = len(results)
    errs = {}
    for r in results:
        if not r["ok"]:
            code = str(r.get("status", "?"))
            errs[code] = errs.get(code, 0) + 1
    return {
        "total": n, "ok": ok, "failed": n - ok, "success_pct": round(ok/n*100, 1),
        "error_codes": errs,
        "latency_ms": {
            "avg": round(statistics.mean(lats), 1),
            "p50": round(statistics.median(lats), 1),
            "p95": round(lats[int(n * 0.95)], 1),
            "p99": round(lats[int(n * 0.99)] if n >= 100 else lats[-1], 1),
            "min": round(min(lats), 1),
            "max": round(max(lats), 1),
        }
    }

results = {}

# Health
try:
    r = requests.get(HEALTH_URL, timeout=10)
    results["health"] = {"status": r.status_code, "ok": r.status_code == 200}
except Exception as e:
    results["health"] = {"status": -1, "ok": False, "error": str(e)}

if not results["health"]["ok"]:
    json.dump(results, sys.stdout, indent=2)
    sys.exit(1)

session = requests.Session()
session.headers.update(HEADERS)

# Baseline
r1 = send_one(session)
results["baseline"] = r1
if not r1["ok"]:
    json.dump(results, sys.stdout, indent=2)
    sys.exit(1)

# Burst: 50 concurrent
t = time.perf_counter()
with ThreadPoolExecutor(max_workers=50) as pool:
    futures = [pool.submit(send_one, session, "burst_test") for _ in range(50)]
    burst = [f.result() for f in as_completed(futures)]
results["burst"] = {"wall_s": round(time.perf_counter()-t, 2), **stats(burst)}

# Sustained: 200 sequential
t = time.perf_counter()
sustained = [send_one(session, f"sustained_{i%5}") for i in range(200)]
wall = time.perf_counter() - t
results["sustained"] = {"wall_s": round(wall, 2), "req_per_s": round(200/wall, 1), **stats(sustained)}

# Concurrent: 20 workers x 25 each
def worker_batch(wid):
    s = requests.Session()
    s.headers.update(HEADERS)
    return [send_one(s, f"worker_{wid}") for _ in range(25)]

t = time.perf_counter()
with ThreadPoolExecutor(max_workers=20) as pool:
    batches = list(pool.map(worker_batch, range(20)))
concurrent = [r for batch in batches for r in batch]
results["concurrent"] = {"wall_s": round(time.perf_counter()-t, 2), **stats(concurrent)}

# Overall
all_r = burst + sustained + concurrent
results["overall"] = stats(all_r)

with open("tmp_stress_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("DONE - results written to tmp_stress_results.json")
