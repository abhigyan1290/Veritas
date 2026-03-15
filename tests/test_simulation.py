"""Closed-environment stress test for Veritas git attribution and regression detection.

No real API calls are made here. CostEvent objects are constructed directly.
SQLiteSink(":memory:") is used — fully isolated per test.

Key invariants:
  - reset_commit_cache() is called after every phase that mutates the git repo.
  - monkeypatch.chdir(repo) aims Veritas's CWD-based resolution at the temp repo.
  - compare_commits returns a plain dict — use result["is_regression"], not .is_regression.
"""

import os
import subprocess
from pathlib import Path

import pytest

from veritas.core import CostEvent
from veritas.engine import compare_commits
from veritas.sinks import SQLiteSink
from veritas.utils import get_current_commit_hash, reset_commit_cache, utc_now_iso
from veritas.utils import _check_dirty  # internal, used for edge-case assertions
import veritas.utils as _vutils


# ─── Git helpers ──────────────────────────────────────────────────────────────

def _git(args: list[str], cwd: Path) -> str:
    """Run a git command in `cwd`, return stdout. Raises on non-zero exit."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def init_repo(path: Path) -> Path:
    """Initialise a brand-new git repo at `path` with author config set."""
    _git(["init"], path)
    _git(["config", "user.email", "sim@example.com"], path)
    _git(["config", "user.name", "Sim Dev"], path)
    return path


def make_commit(repo: Path, filename: str = "code.py", content: str = "x", msg: str = "feat: update") -> str:
    """Write `filename`, stage it, commit, return the 12-char hash."""
    (repo / filename).write_text(content)
    _git(["add", "."], repo)
    _git(["commit", "-m", msg], repo)
    return _git(["rev-parse", "--short=12", "HEAD"], repo)


def make_event(sink: SQLiteSink, code_version: str, cost_usd: float,
               feature: str = "search", model: str = "claude-haiku-4-5-20251001") -> None:
    """Emit one synthetic CostEvent to `sink`. No real API call."""
    event = CostEvent(
        feature=feature,
        model=model,
        tokens_in=100,
        tokens_out=50,
        cache_creation_tokens=0,
        cache_read_tokens=0,
        latency_ms=120.0,
        cost_usd=cost_usd,
        code_version=code_version,
        timestamp=utc_now_iso(),
        status="ok",
        estimated=False,
    )
    sink.emit(event)


# ─── Smoke test: helpers work ──────────────────────────────────────────────────

def test_helpers_smoke(tmp_path, monkeypatch):
    """Helpers can init a repo, make a commit, and emit an event."""
    repo = init_repo(tmp_path)
    monkeypatch.chdir(repo)
    reset_commit_cache()

    hash_ = make_commit(repo, "hello.py", "print('hi')", "feat: hello")
    assert len(hash_) >= 12
    assert all(c in "0123456789abcdef" for c in hash_)

    sink = SQLiteSink(":memory:")
    make_event(sink, hash_, 0.001)
    rows = sink.get_events("search", commit=hash_)
    assert len(rows) == 1
    assert rows[0]["cost_usd"] == pytest.approx(0.001)
    sink.close()

    reset_commit_cache()


# ─── Phase v0.1: Prototype ────────────────────────────────────────────────────

def test_phase_v01_hash_resolution(tmp_path, monkeypatch):
    """v0.1: 2 commits, 5 events. Hash resolves to clean 12-char value."""
    repo = init_repo(tmp_path)
    monkeypatch.chdir(repo)
    reset_commit_cache()

    _hash1 = make_commit(repo, "search.py", "# v0.1 rough", "feat: init search")
    reset_commit_cache()
    hash2 = make_commit(repo, "search.py", "# v0.1 improved", "feat: improve search")
    reset_commit_cache()

    # Veritas resolves against the temp repo because we chdir'd into it
    resolved = get_current_commit_hash()
    assert len(resolved) >= 12, f"hash too short: {resolved!r}"
    assert "+dirty" not in resolved, f"unexpected dirty suffix: {resolved!r}"
    assert resolved == hash2, f"resolved {resolved!r} != committed {hash2!r}"

    sink = SQLiteSink(":memory:")
    for _ in range(5):
        make_event(sink, resolved, cost_usd=0.001)

    rows = sink.get_events("search", commit=resolved)
    assert len(rows) == 5
    sink.close()
    reset_commit_cache()


# ─── Phase v0.2: Iteration — dirty detection ──────────────────────────────────

def test_phase_v02_dirty_detection(tmp_path, monkeypatch):
    """v0.2: dirty suffix appears on uncommitted changes, clears after commit."""
    repo = init_repo(tmp_path)
    monkeypatch.chdir(repo)
    reset_commit_cache()

    # Initial commit to establish HEAD
    make_commit(repo, "search.py", "# base", "feat: base")
    reset_commit_cache()

    # --- Mid-phase: write untracked file (not staged) ---
    (repo / "experiment.py").write_text("# work in progress")
    reset_commit_cache()
    dirty_hash = get_current_commit_hash()
    assert dirty_hash.endswith("+dirty"), f"expected +dirty, got {dirty_hash!r}"

    # --- Emit 10 dirty events ---
    sink = SQLiteSink(":memory:")
    for _ in range(10):
        make_event(sink, dirty_hash, cost_usd=0.001)

    # --- Commit the change — dirty suffix should clear ---
    _git(["add", "."], repo)
    _git(["commit", "-m", "feat: add experiment"], repo)
    reset_commit_cache()
    clean_hash = get_current_commit_hash()
    assert not clean_hash.endswith("+dirty"), f"expected clean hash, got {clean_hash!r}"
    assert len(clean_hash) >= 12

    # --- Make final commit and emit 10 more events ---
    make_commit(repo, "search.py", "# v0.2 final", "feat: v0.2 final")
    reset_commit_cache()
    final_hash = get_current_commit_hash()
    assert not final_hash.endswith("+dirty")
    for _ in range(10):
        make_event(sink, final_hash, cost_usd=0.001)

    clean_rows = sink.get_events("search", commit=final_hash)
    assert len(clean_rows) == 10
    sink.close()
    reset_commit_cache()


# ─── Edge cases ───────────────────────────────────────────────────────────────

def test_edge_packed_refs_fallback(tmp_path, monkeypatch):
    """Fast-path reads packed-refs when loose ref file is deleted (e.g. after git gc).

    packed-refs always stores 40-char full hashes. _resolve_from_dotgit() slices to
    12 chars from that full hash. The test writes a real 40-char hash into packed-refs
    and verifies the resolved value is a 12-char prefix of it.
    """
    repo = init_repo(tmp_path)
    monkeypatch.chdir(repo)
    reset_commit_cache()

    make_commit(repo, "a.py", "x", "feat: first")
    reset_commit_cache()

    # Get the FULL 40-char hash (what git actually stores in packed-refs)
    full_40 = _git(["rev-parse", "HEAD"], repo)
    assert len(full_40) == 40, f"expected 40-char hash, got {len(full_40)}: {full_40!r}"

    # Simulate git gc: write packed-refs with the 40-char hash, delete loose ref.
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
    loose_ref = repo / ".git" / "refs" / "heads" / branch
    packed_refs = repo / ".git" / "packed-refs"

    packed_refs.write_text(
        f"# pack-refs with: peeled fully-peeled sorted\n{full_40} refs/heads/{branch}\n"
    )
    loose_ref.unlink()  # delete the loose ref — only packed-refs remains

    reset_commit_cache()
    resolved = get_current_commit_hash()
    # _resolve_from_dotgit() slices full_40[:12] — so resolved must be a 12-char prefix
    assert "+dirty" not in resolved
    assert len(resolved) >= 12, f"packed-refs resolution too short: {resolved!r}"
    assert full_40.startswith(resolved), \
        f"full hash {full_40!r} should start with resolved {resolved!r}"
    reset_commit_cache()


def test_edge_unborn_head(tmp_path, monkeypatch):
    """Unborn HEAD (empty repo, no commits): hash is 'unknown', dirty check is False."""
    repo = init_repo(tmp_path)
    monkeypatch.chdir(repo)
    reset_commit_cache()

    # No commits made — HEAD points to a ref that doesn't exist yet
    resolved = get_current_commit_hash()
    assert resolved == "unknown", f"expected 'unknown' for unborn HEAD, got {resolved!r}"

    dirty = _check_dirty()
    assert dirty is False, "unborn HEAD should not be detected as dirty"
    reset_commit_cache()


def test_edge_compare_commits_unknown_raises(tmp_path, monkeypatch):
    """compare_commits raises ValueError before querying sink when either commit is 'unknown'."""
    sink = SQLiteSink(":memory:")
    # Even if events exist with code_version='unknown', the guard fires first
    make_event(sink, "unknown", 0.05)
    make_event(sink, "abc123456789", 0.05)

    with pytest.raises(ValueError, match="VERITAS_CODE_VERSION"):
        compare_commits(sink, "search", "unknown", "abc123456789")

    with pytest.raises(ValueError, match="VERITAS_CODE_VERSION"):
        compare_commits(sink, "search", "abc123456789", "unknown")

    sink.close()


def test_edge_compare_commits_no_events_raises(tmp_path):
    """compare_commits raises ValueError when valid hash has no events (distinct from 'unknown' guard)."""
    sink = SQLiteSink(":memory:")
    # Only commit_a has events; commit_b has none
    make_event(sink, "abc123456789", 0.05)

    with pytest.raises(ValueError, match="No data found"):
        compare_commits(sink, "search", "abc123456789", "def456789012")

    sink.close()


# ─── Phases v0.3 + v0.4: Regression then Hotfix ──────────────────────────────

def test_phase_v03_regression_and_v04_hotfix(tmp_path, monkeypatch):
    """v0.3: bad prompt → cost spike → regression detected.
    v0.4: hotfix → cost normalises → regression clears."""
    repo = init_repo(tmp_path)
    monkeypatch.chdir(repo)
    reset_commit_cache()

    # Need a v0.2 baseline hash to compare against
    make_commit(repo, "search.py", "# v0.2 prompt = simple", "feat: v0.2 baseline")
    reset_commit_cache()
    v02_hash = get_current_commit_hash()
    assert not v02_hash.endswith("+dirty")

    sink = SQLiteSink(":memory:")

    # v0.2 baseline: 20 events @ $0.001 avg
    for _ in range(20):
        make_event(sink, v02_hash, cost_usd=0.001)

    # --- v0.3: bad prompt inflates cost 100x ---
    make_commit(repo, "search.py", "# v0.3 prompt = verbose (bad)", "feat: v0.3 bad prompt")
    reset_commit_cache()
    v03_hash = get_current_commit_hash()
    assert v03_hash != v02_hash
    assert not v03_hash.endswith("+dirty")

    for _ in range(30):
        make_event(sink, v03_hash, cost_usd=0.10)  # $0.10 avg; delta=$0.099, ~9900%

    result_03 = compare_commits(sink, "search", v02_hash, v03_hash)
    assert result_03["is_regression"] is True, \
        f"expected regression, got: {result_03}"
    assert result_03["delta_cost_usd"] > 0.01   # absolute threshold
    assert result_03["percent_change"] > 0.10   # percent threshold
    assert result_03["commit_a_stats"]["count"] == 20
    assert result_03["commit_b_stats"]["count"] == 30

    # --- v0.4: hotfix restores normal cost ---
    make_commit(repo, "search.py", "# v0.4 prompt = fixed", "fix: restore prompt")
    reset_commit_cache()
    v04_hash = get_current_commit_hash()
    assert v04_hash not in (v02_hash, v03_hash)

    for _ in range(30):
        make_event(sink, v04_hash, cost_usd=0.001)  # back to normal

    result_04 = compare_commits(sink, "search", v03_hash, v04_hash)
    assert result_04["is_regression"] is False, \
        f"expected no regression after hotfix, got: {result_04}"
    assert result_04["delta_cost_usd"] < 0  # cost actually dropped

    sink.close()
    reset_commit_cache()


# ─── Phase v0.5: Scale — 205 events, SQLite batch + remainder flush ───────────

def test_phase_v05_scale_load(monkeypatch):
    """v0.5: 205 synthetic events via VERITAS_CODE_VERSION injection.

    205 = 8 × 25 (batch) + 5 (remainder flushed by close()).
    Both flush paths exercised. No real git repo needed — env-var overrides git.
    This test verifies no crash occurs during 205 emits + close on :memory: sink.
    """
    synthetic_version = "scale_injection_v05"
    monkeypatch.setenv("VERITAS_CODE_VERSION", synthetic_version)
    reset_commit_cache()

    sink = SQLiteSink(":memory:")

    for i in range(205):
        make_event(sink, synthetic_version, cost_usd=0.001)

    # Flush remainder (5 events) via close() — verifies no crash
    sink.close()
    reset_commit_cache()


def test_phase_v05_scale_count(tmp_path, monkeypatch):
    """Verify all 205 events are persisted — batch commits + remainder flush — no data loss."""
    synthetic_version = "scale_injection_v05"
    monkeypatch.setenv("VERITAS_CODE_VERSION", synthetic_version)
    reset_commit_cache()

    db_path = tmp_path / "scale_test.db"
    sink = SQLiteSink(str(db_path))

    for _ in range(205):
        make_event(sink, synthetic_version, cost_usd=0.001)

    sink.close()  # flushes remaining 5 events (205 % 25 = 5)

    # Verify via direct sqlite3 query
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    count = conn.execute(
        "SELECT COUNT(*) FROM events WHERE code_version = ?", (synthetic_version,)
    ).fetchone()[0]
    conn.close()

    assert count == 205, f"expected 205 events, got {count}"
    monkeypatch.delenv("VERITAS_CODE_VERSION", raising=False)
    reset_commit_cache()
