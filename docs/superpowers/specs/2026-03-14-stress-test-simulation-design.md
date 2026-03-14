# Veritas Stress Test Simulation — Design Spec
Date: 2026-03-14

## Overview

A closed-environment, locally debuggable stress test for the Veritas AI cost attribution SDK.
The goal: simulate a solo developer iterating on an AI feature from prototype to production scale,
and verify that Veritas correctly attributes costs to git commits, detects regressions, and
survives load without crashing.

## Scenario Narrative

A solo developer builds and iterates on an AI-powered search feature across five phases:

| Phase | Git state | Event volume | Primary assertion |
|-------|-----------|--------------|-------------------|
| v0.1 — Prototype | 2 commits, clean | 5 events | Hash resolved correctly, clean suffix |
| v0.2 — Iteration | 3 commits, dirty mid-phase | 20 events | Dirty suffix appears then clears on commit |
| v0.3 — Regression | 1 commit (bad prompt) | 30 events | `compare_commits()` detects cost spike |
| v0.4 — Hotfix | 1 commit | 30 events | Regression clears after fix |
| v0.5 — Scale | 1 commit + env-var injection | 200 events | No data loss, no crash, query stays fast |

## Environment Approach: Hybrid

- **Real git operations** (phases v0.1–v0.4): a temporary git repo is created per run, with real
  commits made via subprocess. This exercises hash resolution end-to-end: fast-path
  (`.git/HEAD` + loose refs + packed-refs fallback), dirty detection via
  `git status --porcelain`, and `compare_commits()` over actual recorded events.
- **Synthetic injection** (v0.5 load phase): `VERITAS_CODE_VERSION` is set via env var to avoid
  creating 200 commits. This is the production pattern for Docker/CI deployments.

## Two Deliverables

### 1. `tests/test_simulation.py` — Pytest Correctness Suite

- **When to run**: `pytest tests/test_simulation.py` (included in full test run)
- **Sink**: `SQLiteSink(":memory:")` — no disk I/O, fully isolated per run
- **API calls**: Synthetic (no real Anthropic calls) — deterministic, fast, CI-safe
- **Edge cases exercised within phases**:
  - `+dirty` suffix appears when working tree modified, clears after commit
  - Packed-refs fallback (simulated by removing loose ref file after commit)
  - Unborn HEAD on empty repo returns `"unknown"` gracefully
  - `compare_commits("unknown", ...)` raises `ValueError` before querying sink
  - 200 events across v0.5 exercises SQLite batch commit logic (BATCH_SIZE=25 → 8 flushes)
- **Assertions**:
  - v0.1: `code_version` matches 12-char git hash, no `+dirty`
  - v0.2: mid-phase `code_version` ends in `+dirty`, post-commit does not
  - v0.3: `compare_commits(v0.2_hash, v0.3_hash).is_regression == True`
  - v0.4: `compare_commits(v0.3_hash, v0.4_hash).is_regression == False`
  - v0.5: all 200 events persisted, `SELECT COUNT(*)` matches

### 2. `scripts/simulate.py` — End-to-End Narrative Script

- **When to run**: `python scripts/simulate.py`
- **Sink**: `SQLiteSink("simulation.db")` + optional `HttpSink(localhost:8000)` in parallel
- **API calls**: Real Claude API (`claude-haiku-4-5-20251001`), loaded from `.env`
- **HttpSink**: wrapped in try/except — if server is unreachable, script continues with SQLite only
- **Output**: live phase-by-phase narrative + final summary table:
  ```
  Phase     Commit        Events  Avg Cost    Regression?
  v0.1      abc123456789       5  $0.0002     —
  v0.2      def456789abc      20  $0.0003     —
  v0.3      bad123456789      30  $0.0012     YES
  v0.4      fix987654321      30  $0.0003     NO
  v0.5      fix987654321     200  $0.0003     NO (scale)
  ```

## Data Flow

```
scripts/simulate.py
  ├── tempfile.mkdtemp()          # isolated git repo
  ├── subprocess git commits      # real hash resolution
  ├── @track(feature="search")    # CostEvent produced per call
  │     └── anthropic.Anthropic() # real API call (haiku model)
  ├── SQLiteSink("simulation.db") # persists events, enables compare_commits()
  └── HttpSink("localhost:8000")  # live server feed (optional, fails gracefully)

tests/test_simulation.py
  ├── tmp_path fixture            # pytest-managed temp dir
  ├── subprocess git commits      # same real hash resolution
  ├── synthetic CostEvent()       # no API calls, deterministic costs
  └── SQLiteSink(":memory:")      # isolated, no disk state between tests
```

## Error Handling and Crash Resistance

| Failure mode | Behaviour |
|---|---|
| Server not running (HttpSink) | `try/except ImportError + ConnectionError` on init; script skips HttpSink and logs warning |
| Git binary missing | `_resolve_via_subprocess()` returns `None`; falls back to `"unknown"` — no crash |
| Unborn HEAD (empty repo) | `git status --porcelain` exits 0 with empty output; correctly detected as clean |
| 200 events (load) | SQLite batch commits every 25; `close()` flushes remainder — no events lost |
| `compare_commits("unknown", ...)` | `ValueError` raised immediately — tested explicitly |
| Packed-refs only (no loose ref) | `_read_packed_ref()` parses file; returns correct hash |

## Model Choice

`claude-haiku-4-5-20251001` — lowest cost, still provides real usage tokens for attribution.
Prompts in the simulation are short (1-2 sentences) to minimise spend during testing.

## Files to Create

```
tests/test_simulation.py      # pytest correctness suite (~200 lines)
scripts/simulate.py           # standalone narrative script (~180 lines)
```

No new dependencies. Existing `anthropic` and `veritas` packages are sufficient.

## Success Criteria

- `pytest tests/test_simulation.py` passes in under 30 seconds with no real API calls
- `python scripts/simulate.py` completes end-to-end, prints summary table, exits 0
- If `localhost:8000` is not running, script still completes (graceful HttpSink skip)
- No uncaught exceptions across all 5 phases under any ordering
- SQLite event count matches emitted count exactly after v0.5 load phase
