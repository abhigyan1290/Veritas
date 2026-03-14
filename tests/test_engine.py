"""Tests for veritas change detection engine."""

import pytest
from veritas.engine import compare_commits, _compute_averages, strip_dirty_suffix, REGRESSION_ABSOLUTE_THRESHOLD_USD, REGRESSION_PERCENT_THRESHOLD

class MockSink:
    def __init__(self, data):
        self.data = data
        
    def get_events(self, feature, commit=None, since_iso=None):
        return [
            e for e in self.data 
            if e["feature"] == feature and e["code_version"] == commit
        ]

def test_compute_averages():
    events = [
        {"cost_usd": 0.10, "tokens_in": 100, "tokens_out": 50, "latency_ms": 1000},
        {"cost_usd": 0.20, "tokens_in": 200, "tokens_out": 100, "latency_ms": 2000},
    ]
    avg = _compute_averages(events)
    assert avg["count"] == 2
    assert avg["avg_cost_usd"] == pytest.approx(0.15)
    assert avg["avg_tokens_in"] == 150.0
    assert avg["avg_tokens_out"] == 75.0
    assert avg["avg_latency_ms"] == 1500.0


def test_compare_commits_raises_value_error_if_no_data():
    sink = MockSink([])
    with pytest.raises(ValueError, match="No data found for commit"):
        compare_commits(sink, "search", "commitA", "commitB")

def test_compare_commits_detects_regression():
    data = [
        # Commit A (Base) averages out to $0.05
        {"feature": "search", "code_version": "A", "cost_usd": 0.04, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
        {"feature": "search", "code_version": "A", "cost_usd": 0.06, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
        # Commit B (Regressed) averages out to $0.05 + absolute threshold (e.g., $0.062)
        {"feature": "search", "code_version": "B", "cost_usd": 0.05 + REGRESSION_ABSOLUTE_THRESHOLD_USD + 0.005, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
        {"feature": "search", "code_version": "B", "cost_usd": 0.05 + REGRESSION_ABSOLUTE_THRESHOLD_USD + 0.005, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
    ]
    sink = MockSink(data)
    res = compare_commits(sink, "search", "A", "B")
    
    assert res["is_regression"] is True
    assert res["commit_a_stats"]["count"] == 2
    assert res["commit_b_stats"]["count"] == 2
    assert res["delta_cost_usd"] > REGRESSION_ABSOLUTE_THRESHOLD_USD
    assert res["percent_change"] > REGRESSION_PERCENT_THRESHOLD

def test_compare_commits_ignores_small_absolute_deltas():
    # Test that even if it spikes 50% ($0.001 to $0.0015), if the absolute
    # dollar amount is below threshold, it doesn't trigger.
    data = [
        {"feature": "search", "code_version": "A", "cost_usd": 0.001, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
        {"feature": "search", "code_version": "B", "cost_usd": 0.002, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
    ]
    sink = MockSink(data)
    res = compare_commits(sink, "search", "A", "B")
    
    # It doubled (>10%), but it only went up $0.001 which is < Absolute Threshold
    assert res["percent_change"] == 1.0 # 100%
    assert res["is_regression"] is False # Below absolute threshold

def test_compare_commits_ignores_small_percent_change():
    # Test that if it spikes by a massive absolute amount (e.g., $10.00 -> $10.05),
    # but the percentage change is below the threshold, it doesn't trigger.
    data = [
        {"feature": "search", "code_version": "A", "cost_usd": 10.00, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
        {"feature": "search", "code_version": "B", "cost_usd": 10.05, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
    ]
    sink = MockSink(data)
    res = compare_commits(sink, "search", "A", "B")
    
    # It went up by $0.05 (> Absolute Threshold) but that's only a 0.5% increase (< Percent Threshold)
    assert res["delta_cost_usd"] == pytest.approx(0.05)
    assert res["percent_change"] == pytest.approx(0.005) # 0.5%
    assert res["is_regression"] is False # Below percentage threshold


# ─────────────────────────────────────────────────────────────────────────────
# New tests for dirty suffix handling
# ─────────────────────────────────────────────────────────────────────────────

def test_strip_dirty_suffix_removes_dirty():
    """strip_dirty_suffix removes +dirty."""
    assert strip_dirty_suffix("abc1234+dirty") == "abc1234"

def test_strip_dirty_suffix_noop_on_clean():
    """strip_dirty_suffix is a no-op on clean hashes."""
    assert strip_dirty_suffix("abc1234") == "abc1234"

def test_compare_commits_excludes_dirty_by_default():
    """By default, +dirty events are filtered out of comparison."""
    data = [
        {"feature": "search", "code_version": "abc1234", "cost_usd": 0.05, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
        {"feature": "search", "code_version": "abc1234+dirty", "cost_usd": 0.50, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
        {"feature": "search", "code_version": "def5678", "cost_usd": 0.06, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
    ]
    sink = MockSink(data)
    res = compare_commits(sink, "search", "abc1234", "def5678")

    # The $0.50 dirty event should be excluded from commit A stats
    assert res["commit_a_stats"]["count"] == 1
    assert res["commit_a_stats"]["avg_cost_usd"] == pytest.approx(0.05)

def test_compare_commits_includes_dirty_when_requested():
    """With include_dirty=True, +dirty events are included."""
    data = [
        {"feature": "search", "code_version": "abc1234", "cost_usd": 0.05, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
        {"feature": "search", "code_version": "abc1234+dirty", "cost_usd": 0.50, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
        {"feature": "search", "code_version": "def5678", "cost_usd": 0.06, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
    ]
    sink = MockSink(data)
    res = compare_commits(sink, "search", "abc1234", "def5678", include_dirty=True)

    # With include_dirty, both clean ($0.05) and dirty ($0.50) events are included
    assert res["commit_a_stats"]["count"] == 2
    assert res["commit_a_stats"]["avg_cost_usd"] == pytest.approx(0.275)


# ─────────────────────────────────────────────────────────────────────────────
# New tests for tag filtering
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Guard: "unknown" commit hashes
# ─────────────────────────────────────────────────────────────────────────────

def test_compare_commits_raises_for_unknown_commit_a():
    """compare_commits raises before querying sink when commit_a is 'unknown'.

    The critical case: events ARE stored with code_version='unknown' (Docker/CI
    without VERITAS_CODE_VERSION set), but comparing them is meaningless.
    The guard must fire BEFORE the sink query, not fall through to "No data".
    """
    data = [
        # Events recorded with unknown version — common in un-configured deployments
        {"feature": "search", "code_version": "unknown", "cost_usd": 0.05,
         "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
        {"feature": "search", "code_version": "abc123456789", "cost_usd": 0.05,
         "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
    ]
    sink = MockSink(data)
    with pytest.raises(ValueError, match="VERITAS_CODE_VERSION"):
        compare_commits(sink, "search", "unknown", "abc123456789")


def test_compare_commits_raises_for_unknown_commit_b():
    """compare_commits raises before querying sink when commit_b is 'unknown'."""
    data = [
        {"feature": "search", "code_version": "unknown", "cost_usd": 0.08,
         "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
        {"feature": "search", "code_version": "abc123456789", "cost_usd": 0.05,
         "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
    ]
    sink = MockSink(data)
    with pytest.raises(ValueError, match="VERITAS_CODE_VERSION"):
        compare_commits(sink, "search", "abc123456789", "unknown")


def test_compare_commits_raises_for_both_unknown():
    """compare_commits raises when both commits are 'unknown' — not silent garbage."""
    data = [
        {"feature": "search", "code_version": "unknown", "cost_usd": 0.05,
         "tokens_in": 10, "tokens_out": 10, "latency_ms": 1},
    ]
    sink = MockSink(data)
    with pytest.raises(ValueError, match="VERITAS_CODE_VERSION"):
        compare_commits(sink, "search", "unknown", "unknown")


from veritas.engine import filter_events_by_tags

def test_filter_events_by_tags_empty():
    """If no tags are provided, returns all events."""
    events = [{"tags": {"a": "1"}}, {"tags": {"b": "2"}}]
    assert filter_events_by_tags(events, None) == events
    assert filter_events_by_tags(events, {}) == events


def test_filter_events_by_tags_matches():
    """Returns only events that match all provided tags."""
    events = [
        {"id": 1, "tags": {"tenant": "acme", "env": "prod"}},
        {"id": 2, "tags": {"tenant": "acme", "env": "dev"}},
        {"id": 3, "tags": {"tenant": "stark", "env": "prod"}},
        {"id": 4}, # No tags
    ]
    
    # Filter by one tag
    res1 = filter_events_by_tags(events, {"tenant": "acme"})
    assert len(res1) == 2
    assert res1[0]["id"] == 1
    assert res1[1]["id"] == 2
    
    # Filter by multiple tags (AND logic)
    res2 = filter_events_by_tags(events, {"tenant": "acme", "env": "prod"})
    assert len(res2) == 1
    assert res2[0]["id"] == 1


def test_compare_commits_with_tags():
    """compare_commits correctly passes tags down to filter events."""
    import json
    data = [
        # JSON encoded tags to simulate SQLite returns
        {"feature": "search", "code_version": "A", "cost_usd": 0.05, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1, "tags": json.dumps({"tenant": "acme"})},
        {"feature": "search", "code_version": "A", "cost_usd": 0.15, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1, "tags": json.dumps({"tenant": "stark"})},
        {"feature": "search", "code_version": "B", "cost_usd": 0.05, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1, "tags": json.dumps({"tenant": "acme"})},
        {"feature": "search", "code_version": "B", "cost_usd": 0.50, "tokens_in": 10, "tokens_out": 10, "latency_ms": 1, "tags": json.dumps({"tenant": "stark"})},
    ]
    sink = MockSink(data)
    
    # Filter for acme. Should compare $0.05 vs $0.05 (no regression)
    res = compare_commits(sink, "search", "A", "B", tags={"tenant": "acme"})
    assert res["commit_a_stats"]["count"] == 1
    assert res["commit_a_stats"]["avg_cost_usd"] == pytest.approx(0.05)
    assert res["commit_b_stats"]["avg_cost_usd"] == pytest.approx(0.05)
    assert res["is_regression"] is False
    
    # Filter for stark. Should compare $0.15 vs $0.50 (regression)
    res2 = compare_commits(sink, "search", "A", "B", tags={"tenant": "stark"})
    assert res2["commit_a_stats"]["avg_cost_usd"] == pytest.approx(0.15)
    assert res2["commit_b_stats"]["avg_cost_usd"] == pytest.approx(0.50)
    assert res2["is_regression"] is True

