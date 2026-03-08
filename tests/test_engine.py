"""Tests for veritas change detection engine."""

import pytest
from veritas.engine import compare_commits, _compute_averages, REGRESSION_ABSOLUTE_THRESHOLD_USD, REGRESSION_PERCENT_THRESHOLD

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
