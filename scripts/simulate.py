#!/usr/bin/env python3
"""Veritas stress test simulation — solo developer, 5 phases.

Usage:
    python scripts/simulate.py

Requires:
    - ANTHROPIC_API_KEY in .env (or environment)
    - anthropic package: pip install anthropic
    - veritas installed: pip install -e .

Emits real Claude API calls (claude-haiku-4-5-20251001) and tracks costs
in simulation.db. Also forwards events to localhost:8000 if requests is
installed and the server is running.
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

# ─── Load .env from project root ──────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent


def _load_env():
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


_load_env()

# ─── Imports (after .env is loaded) ───────────────────────────────────────────

try:
    import anthropic as _anthropic
except ImportError:
    print("ERROR: anthropic not installed. Run: pip install anthropic")
    sys.exit(1)

from veritas.core import CostEvent
from veritas.engine import compare_commits
from veritas.pricing import compute_cost
from veritas.sinks import SQLiteSink, HttpSink
from veritas.utils import get_current_commit_hash, reset_commit_cache, utc_now_iso

# ─── Git helpers ──────────────────────────────────────────────────────────────


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {args} failed (exit {result.returncode}):\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def init_repo(path: Path) -> Path:
    _git(["init"], path)
    _git(["config", "user.email", "sim@example.com"], path)
    _git(["config", "user.name", "Sim Dev"], path)
    return path


def make_commit(repo: Path, filename: str, content: str, msg: str) -> str:
    (repo / filename).write_text(content)
    _git(["add", "."], repo)
    _git(["commit", "-m", msg], repo)
    return _git(["rev-parse", "--short=12", "HEAD"], repo)


# ─── Sink setup ───────────────────────────────────────────────────────────────


def build_sinks() -> tuple[SQLiteSink, list]:
    """Returns (sqlite_sink, list_of_all_sinks). HttpSink added if requests available."""
    db_sink = SQLiteSink(str(ROOT / "simulation.db"))

    http_sink = None
    endpoint = os.environ.get("VERITAS_API_URL", "http://localhost:8000/api/v1/events")
    api_key = os.environ.get("VERITAS_API_KEY", "sk-vrt-demo")
    try:
        http_sink = HttpSink(endpoint_url=endpoint, api_key=api_key)
        print(f"[sim] HttpSink active -> {endpoint}")
    except ImportError:
        print("[sim] Warning: 'requests' not installed — HttpSink skipped. "
              "Install with: pip install requests")

    all_sinks = [db_sink] + ([http_sink] if http_sink else [])
    return db_sink, all_sinks


def emit_to_all(sinks, event: CostEvent) -> None:
    for sink in sinks:
        sink.emit(event)


# ─── Claude API call (real) ───────────────────────────────────────────────────


def call_claude(prompt: str, api_key: str, model: str = "claude-haiku-4-5-20251001"):
    """Make one real API call. Returns the Message object."""
    client = _anthropic.Anthropic(api_key=api_key)
    return client.messages.create(
        model=model,
        max_tokens=50,
        messages=[{"role": "user", "content": prompt}],
    )


def run_phase(sinks, code_version: str, prompt: str, n_calls: int,
              cost_override: float | None = None, model: str = "claude-haiku-4-5-20251001") -> dict:
    """Run `n_calls` tracked calls for this phase. Returns phase summary dict.

    `sinks` is the list returned by build_sinks() — all events go to every sink.
    When `cost_override` is set, no real API call is made (synthetic event, scale phase).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and cost_override is None:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    total_cost = 0.0

    for _ in range(n_calls):
        if cost_override is not None:
            event = CostEvent(
                feature="search",
                model=model,
                tokens_in=100,
                tokens_out=50,
                cache_creation_tokens=0,
                cache_read_tokens=0,
                latency_ms=120.0,
                cost_usd=cost_override,
                code_version=code_version,
                timestamp=utc_now_iso(),
                status="ok",
                estimated=False,
            )
            emit_to_all(sinks, event)
            total_cost += cost_override
        else:
            response = call_claude(prompt, api_key, model)
            usage = response.usage
            cost_usd, _ = compute_cost(
                tokens_in=usage.input_tokens,
                tokens_out=usage.output_tokens,
                model=model,
            )
            event = CostEvent(
                feature="search",
                model=model,
                tokens_in=usage.input_tokens,
                tokens_out=usage.output_tokens,
                cache_creation_tokens=0,
                cache_read_tokens=0,
                latency_ms=120.0,
                cost_usd=cost_usd,
                code_version=code_version,
                timestamp=utc_now_iso(),
                status="ok",
                estimated=False,
            )
            emit_to_all(sinks, event)
            total_cost += cost_usd

    avg_cost = total_cost / n_calls if n_calls else 0
    return {"code_version": code_version, "n_calls": n_calls, "avg_cost": avg_cost}


# ─── Phases ───────────────────────────────────────────────────────────────────


def phase_summary_header():
    print(f"\n{'Phase':<10} {'Commit':<22} {'Events':>6}  {'Avg Cost':>10}  Regression?")
    print("-" * 65)


def phase_summary_row(phase: str, summary: dict, regression: bool | None = None):
    reg_str = "-" if regression is None else ("YES" if regression else "NO")
    print(
        f"{phase:<10} {summary['code_version']:<22} {summary['n_calls']:>6}"
        f"  ${summary['avg_cost']:>9.6f}  {reg_str}"
    )


if __name__ == "__main__":
    original_cwd = Path.cwd()
    tmp_dir = tempfile.mkdtemp(prefix="veritas_sim_")
    repo = Path(tmp_dir)

    print(f"\n[sim] Initialising git repo at {repo}")
    init_repo(repo)
    os.chdir(repo)

    db_sink, all_sinks = build_sinks()
    summaries = {}

    try:
        # ── v0.1: Prototype — 2 commits, 5 real API calls ──────────────────
        print("\n[v0.1] Prototype — initial search feature")
        make_commit(repo, "search.py", "# v0.1: naive prompt", "feat: init search v0.1")
        make_commit(repo, "search.py", "# v0.1: add retry logic", "feat: add retry")
        reset_commit_cache()
        v01_hash = get_current_commit_hash()
        print(f"       commit: {v01_hash}")
        summaries["v0.1"] = run_phase(all_sinks, v01_hash,
                                      "What is the capital of France? One word.", n_calls=5)
        phase_summary_header()
        phase_summary_row("v0.1", summaries["v0.1"])

        # ── v0.2: Iteration — 3 commits, 20 real API calls ─────────────────
        print("\n[v0.2] Iteration — refine prompt, add context")
        make_commit(repo, "search.py", "# v0.2: add context window", "feat: v0.2 add context")
        (repo / "experiment.py").write_text("# WIP")  # dirty
        reset_commit_cache()
        mid_hash = get_current_commit_hash()
        print(f"       mid-phase (dirty): {mid_hash}")
        assert mid_hash.endswith("+dirty"), f"expected +dirty: {mid_hash!r}"

        _git(["add", "."], repo)
        _git(["commit", "-m", "feat: save experiment"], repo)
        make_commit(repo, "search.py", "# v0.2: final polish", "feat: v0.2 final")
        reset_commit_cache()
        v02_hash = get_current_commit_hash()
        print(f"       commit (clean): {v02_hash}")
        assert not v02_hash.endswith("+dirty")
        summaries["v0.2"] = run_phase(all_sinks, v02_hash,
                                      "Summarise: AI reduces costs by optimising prompts.", n_calls=20)
        phase_summary_row("v0.2", summaries["v0.2"])

        # ── v0.3: Regression — 1 commit, 30 real API calls (expensive prompt)
        print("\n[v0.3] Regression — verbose prompt inflates cost")
        make_commit(repo, "search.py",
                    "# v0.3: verbose prompt with 500-token system message",
                    "feat: v0.3 verbose prompt")
        reset_commit_cache()
        v03_hash = get_current_commit_hash()
        print(f"       commit: {v03_hash}")
        verbose_prompt = (
            "Please provide a comprehensive, detailed explanation of how modern search engines "
            "work, covering indexing, ranking algorithms, and query processing, in at least "
            "three paragraphs. Be thorough."
        )
        summaries["v0.3"] = run_phase(all_sinks, v03_hash, verbose_prompt, n_calls=30)

        result_03 = compare_commits(db_sink, "search", v02_hash, v03_hash)
        reg_03 = result_03["is_regression"]
        phase_summary_row("v0.3", summaries["v0.3"], regression=reg_03)
        if reg_03:
            print(f"       [!] Regression detected: +{result_03['percent_change']*100:.1f}% cost")
        else:
            print(f"       Cost delta: ${result_03['delta_cost_usd']:.6f} "
                  f"({result_03['percent_change']*100:.1f}%)")

        # ── v0.4: Hotfix — 1 commit, 30 real API calls (restored prompt) ───
        print("\n[v0.4] Hotfix — restore concise prompt")
        make_commit(repo, "search.py",
                    "# v0.4: concise prompt restored",
                    "fix: restore concise search prompt")
        reset_commit_cache()
        v04_hash = get_current_commit_hash()
        print(f"       commit: {v04_hash}")
        summaries["v0.4"] = run_phase(all_sinks, v04_hash,
                                      "What is the capital of France? One word.", n_calls=30)

        result_04 = compare_commits(db_sink, "search", v03_hash, v04_hash)
        reg_04 = result_04["is_regression"]
        phase_summary_row("v0.4", summaries["v0.4"], regression=reg_04)

        # ── v0.5: Scale — env-var injection, 205 synthetic events ───────────
        print("\n[v0.5] Scale — 205 events via VERITAS_CODE_VERSION injection")
        scale_version = "scale_injection_v05"
        os.environ["VERITAS_CODE_VERSION"] = scale_version
        reset_commit_cache()
        avg_cost = summaries["v0.4"]["avg_cost"]
        summaries["v0.5"] = run_phase(all_sinks, scale_version,
                                      "", n_calls=205, cost_override=avg_cost)
        db_sink.close()  # flushes remaining batch (205 % 25 = 5 events)
        phase_summary_row("v0.5", summaries["v0.5"], regression=False)

        # ── Verify count ─────────────────────────────────────────────────────
        conn = sqlite3.connect(str(ROOT / "simulation.db"))
        count = conn.execute(
            "SELECT COUNT(*) FROM events WHERE code_version = ?", (scale_version,)
        ).fetchone()[0]
        conn.close()
        print(f"\n[v0.5] DB count for '{scale_version}': {count} (expected 205)")
        assert count == 205, f"Data loss! Expected 205, got {count}"

        del os.environ["VERITAS_CODE_VERSION"]
        reset_commit_cache()

    except Exception as e:
        print(f"\n[sim] FATAL: {e}")
        raise
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"\n[sim] Cleaned up temp repo. Results saved to simulation.db")
