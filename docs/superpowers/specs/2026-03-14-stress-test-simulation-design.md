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
| v0.1 — Prototype | 2 commits, clean | 5 events | Hash resolved correctly, no `+dirty` suffix |
| v0.2 — Iteration | 3 commits, dirty mid-phase | 20 events | Dirty suffix appears then clears on commit |
| v0.3 — Regression | 1 commit (bad prompt) | 30 events | `compare_commits()` detects cost spike |
| v0.4 — Hotfix | 1 commit | 30 events | Regression clears after fix |
| v0.5 — Scale | env-var injection only | 205 events | No data loss, batch+remainder flush both exercised |

## Environment Approach: Hybrid

- **Real git operations** (phases v0.1–v0.4): a temporary git repo is created per run, with real
  commits made via subprocess. This exercises hash resolution end-to-end: fast-path
  (`.git/HEAD` + loose refs + packed-refs fallback), dirty detection via
  `git status --porcelain`, and `compare_commits()` over actual recorded events.
- **Synthetic injection** (v0.5 load phase): `VERITAS_CODE_VERSION` is set via env var to avoid
  creating 205 commits. This is the production pattern for Docker/CI deployments.

## Hash Resolution — Key Facts

`get_current_commit_hash()` resolves in this priority order:
1. Module-level override (`veritas.init(code_version=...)`)
2. `VERITAS_CODE_VERSION` env var
3. `VERITAS_MOCK_COMMIT` env var (deprecated alias — still checked, included for completeness)
4. Process-lifetime cache (`_commit_cache`)
5. Fast-path: `.git/HEAD` → loose ref → `packed-refs` fallback
6. Subprocess: `git rev-parse --short=12 HEAD`

**Critical test prerequisite**: `_commit_cache` is a module-level global. Between phases that
make real git commits, `reset_commit_cache()` must be called (or `VERITAS_CODE_VERSION` used)
to prevent the first phase's hash being returned for all subsequent phases. The data flow for
`tests/test_simulation.py` must call `reset_commit_cache()` after each phase.

All resolved hashes are minimum 12 hex chars. `_resolve_from_dotgit()` slices to exactly 12
chars; `_resolve_via_subprocess()` may return longer if git needs more chars for uniqueness —
assertions should use `>= 12`, not `== 12`.

## Two Deliverables

### 1. `tests/test_simulation.py` — Pytest Correctness Suite

- **When to run**: `pytest tests/test_simulation.py` (included in full test run)
- **Sink**: `SQLiteSink(":memory:")` — no disk I/O, fully isolated per run
- **API calls**: None. Phases construct `CostEvent(...)` objects directly and call
  `sink.emit(event)`, bypassing `@track` entirely. This makes the no-real-API-calls constraint
  unambiguous and keeps CI safe. Do not wire `@track` into any test phase.
- **Cache reset**: `reset_commit_cache()` called after each phase that makes real git commits.
- **Edge cases exercised within phases**:
  - `+dirty` suffix appears when working tree modified, clears after commit
  - Packed-refs fallback: loose ref file removed after a commit; fast-path must fall back to
    `packed-refs`; returned hash is exactly 12 chars (sliced in `_resolve_from_dotgit`)
  - Unborn HEAD on empty repo: `get_current_commit_hash()` returns `"unknown"` (both
    `_resolve_from_dotgit` and subprocess return `None` on a repo with no commits);
    `_check_dirty()` returns `False` (clean) since `git status --porcelain` exits 0
    with empty output on unborn HEAD — these are two separate behaviours
  - `compare_commits(sink, "search", "unknown", "abc123...")` raises `ValueError` before
    querying sink
  - `compare_commits(sink, "search", "abc123...", "def456...")` raises `ValueError` when no
    events exist for a valid hash (distinct code path from "unknown" guard)
  - 205 events across v0.5: 8 full batch commits (8×25=200) + 1 remainder flush via `close()`
    — both the batch path and the remainder path are exercised
- **Assertions use dict access, not attribute access** — `compare_commits` returns a plain `dict`:
  - v0.1: `len(code_version) >= 12`, no `+dirty` in value
  - v0.2: mid-phase `code_version.endswith("+dirty") is True`, post-commit does not
  - v0.3: `result["is_regression"] is True` where `result = compare_commits(sink, "search", v0.2_hash, v0.3_hash)`
  - v0.4: `result["is_regression"] is False` where `result = compare_commits(sink, "search", v0.3_hash, v0.4_hash)`
  - v0.5: `SELECT COUNT(*) FROM events WHERE code_version = ?` returns 205

### 2. `scripts/simulate.py` — End-to-End Narrative Script

- **When to run**: `python scripts/simulate.py`
- **Sink**: `SQLiteSink("simulation.db")` always; `HttpSink(localhost:8000)` optionally in parallel
- **API calls**: Real Claude API (`claude-haiku-4-5-20251001`), loaded from `.env`
- **Cache reset**: `reset_commit_cache()` called between each phase (same as test suite)
- **HttpSink graceful skip**: `HttpSink.__init__` raises `ImportError` if `requests` is not
  installed; it does NOT raise at construction if the server is unreachable (the daemon thread
  swallows all network errors silently inside `_flush_loop`). The script wraps HttpSink
  construction in `try/except ImportError` only. Server-unreachable failures are silently
  handled by the existing HttpSink implementation — no additional handling needed.
- **Output**: live phase-by-phase narrative + final summary table:
  ```
  Phase     Commit              Events  Avg Cost    Regression?
  v0.1      abc123456789             5  $0.0002     —
  v0.2      def456789abc            20  $0.0003     —
  v0.3      bad123456789            30  $0.0012     YES
  v0.4      fix987654321            30  $0.0003     NO
  v0.5      scale_injection_v05    205  $0.0003     NO (scale)
  ```
  Note: v0.5 shows the injected `VERITAS_CODE_VERSION` value, not a git hash — making it clear
  env-var injection is active and v0.5 events are stored under a distinct identity from v0.4.

## Data Flow

```
scripts/simulate.py
  ├── tempfile.mkdtemp()            # isolated git repo
  ├── subprocess git commits        # real hash resolution (phases v0.1–v0.4)
  ├── reset_commit_cache()          # must be called between each phase
  ├── @track(feature="search")      # CostEvent produced per API call
  │     └── anthropic.Anthropic()   # real API call (haiku model)
  ├── os.environ["VERITAS_CODE_VERSION"] = "scale_injection_v05"  # v0.5 only
  ├── SQLiteSink("simulation.db")   # persists events, enables compare_commits()
  └── try: HttpSink("localhost:8000")  # live server feed — ImportError caught; network
        except ImportError: skip    #   failures swallowed by daemon thread internally

tests/test_simulation.py
  ├── tmp_path fixture              # pytest-managed temp dir, auto-cleaned
  ├── subprocess git commits        # same real hash resolution (phases v0.1–v0.4)
  ├── reset_commit_cache()          # called after each phase
  ├── CostEvent(...); sink.emit()   # no @track, no API calls — fully synthetic
  └── SQLiteSink(":memory:")        # isolated, no disk state between tests
```

## Error Handling and Crash Resistance

| Failure mode | Behaviour |
|---|---|
| Server not running (HttpSink) | Daemon thread in `_flush_loop` swallows all exceptions silently — no crash, events dropped |
| `requests` not installed (HttpSink) | `HttpSink.__init__` raises `ImportError`; `simulate.py` catches this and skips HttpSink |
| Git binary missing | `_resolve_via_subprocess()` returns `None`; fast-path also returns `None`; result is `"unknown"` — no crash |
| Unborn HEAD — hash | Both fast-path and subprocess return `None`; `get_current_commit_hash()` returns `"unknown"` |
| Unborn HEAD — dirty check | `git status --porcelain` exits 0, empty output; `_check_dirty()` returns `False` (clean) |
| 205 events (load) | 8 full batch commits (every 25); `close()` flushes remaining 5 — both paths exercised |
| `compare_commits("unknown", ...)` | `ValueError` raised immediately before sink query — tested explicitly |
| `compare_commits` valid hash, no events | `ValueError` raised ("No data found") — distinct code path, tested separately |
| Packed-refs only (no loose ref) | `_read_packed_ref()` parses `packed-refs` file; returns 12-char hash |

## Model Choice

`claude-haiku-4-5-20251001` — lowest cost, still provides real usage tokens for attribution.
Prompts in the simulation are short (1-2 sentences) to minimise spend during testing.

## Files to Create

```
tests/test_simulation.py      # pytest correctness suite (~220 lines)
scripts/simulate.py           # standalone narrative script (~200 lines)
```

No new dependencies. Existing `anthropic` and `veritas` packages are sufficient.

## Success Criteria

- `pytest tests/test_simulation.py` passes in under 30 seconds with no real API calls
- `python scripts/simulate.py` completes end-to-end, prints summary table, exits 0
- If `localhost:8000` is not running, script still completes (HttpSink daemon thread handles it)
- If `requests` is not installed, script prints a warning and continues with SQLite only
- No uncaught exceptions across all 5 phases
- SQLite event count matches emitted count exactly after v0.5 load phase (205 rows)
