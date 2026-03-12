# Veritas — Latency Optimizations

Four targeted fixes to eliminate unnecessary latency from the SDK hot path and the dashboard request path.

---

## Changes

### 1. Cache the git commit hash — `veritas/utils.py`

**Problem:** `get_current_commit_hash()` spawned a `git rev-parse` subprocess on every single AI call. The commit hash cannot change while the process is running.

---

### 2. SQLiteSink WAL mode + batch commits — `veritas/sinks.py`

**Problem:** Every `emit()` called `sqlite3.commit()` immediately, triggering an `fsync` to disk. On typical hardware this costs 2–5ms per event.

---

### 3. HttpSink async queue — `veritas/sinks.py`

**Problem:** `emit()` did a synchronous `requests.post()` with a 2-second timeout. Every AI call in the host application blocked waiting for the Veritas server to respond before returning.

---

### 4. Remove `ensure_demo_tenant` from dashboard route — `server/routes/dashboard.py`

**Problem:** `ensure_demo_tenant()` was called on every `GET /` (dashboard page load). Each call ran `bcrypt.hash()` (~170ms) plus 2 SELECT queries and a possible UPDATE commit.

---

## Benchmark Results

Measured with `scripts/benchmark_latency.py` on Python 3.11, Windows 11.

| Component | Before | After | Improvement |
|---|---|---|---|
| `get_current_commit_hash()` | 17.08 ms | 0.35 ms | **98% faster** |
| `SQLiteSink.emit()` | 2.16 ms | 0.01 ms | **99.6% faster** |
| `HttpSink.emit()` caller latency | 42.28 ms | ~0 ms | **non-blocking** |
| `ensure_demo_tenant()` per request | 180.86 ms | 0 ms | **eliminated** |

HttpSink note: the 42ms baseline used a local fake server with 30ms artificial delay to simulate real network conditions.

---

## Test Coverage

All 44 tests pass after the changes. The 3 `test_utils.py` tests that mock `subprocess.run` were updated to also reset `_commit_cache` to `None` via `monkeypatch` so the mock is actually reached.

