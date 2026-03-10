"""Tests for pricing module."""

import pytest

from veritas.pricing import PRICING_TABLE, compute_cost


def test_compute_cost_known_model():
    """compute_cost returns correct cost for claude-3-5-sonnet."""
    # 1000 input + 500 output at claude-3-5-sonnet: $3/1M in, $15/1M out
    # = 0.003 + 0.0075 = 0.0105
    cost, estimated = compute_cost(1000, 500, "claude-3-5-sonnet")
    assert estimated is False
    assert abs(cost - 0.0105) < 1e-9


def test_compute_cost_claude_haiku():
    """compute_cost returns correct cost for claude-3-haiku."""
    # 100 input + 50 output at claude-3-haiku: $0.25/1M in, $1.25/1M out
    # = 0.000025 + 0.0000625 = 0.0000875
    cost, estimated = compute_cost(100, 50, "claude-3-haiku")
    assert estimated is False
    assert abs(cost - 0.0000875) < 1e-6


def test_compute_cost_versioned_model():
    """Versioned model names resolve to base model pricing."""
    cost, estimated = compute_cost(1000, 500, "claude-3-5-sonnet-20241022")
    assert estimated is False
    assert abs(cost - 0.0105) < 1e-9


def test_compute_cost_csv_dashboard_model():
    """Dashboard CSV formats like 'Claude Sonnet 4' resolve correctly."""
    cost, estimated = compute_cost(1000, 500, "Claude Sonnet 4")
    assert estimated is False
    # Using claude-sonnet-4 pricing: $3/1M in, $15/1M out -> 0.003 + 0.0075 = 0.0105
    assert abs(cost - 0.0105) < 1e-9


def test_compute_cost_unknown_model():
    """Unknown model uses fallback rate and sets estimated=True."""
    cost, estimated = compute_cost(1000, 500, "unknown-model-xyz")
    assert estimated is True
    # Should use claude-3-5-sonnet as fallback
    expected, _ = compute_cost(1000, 500, "claude-3-5-sonnet")
    assert cost == expected


def test_compute_cost_zero_tokens():
    """Zero tokens yields zero cost."""
    cost, estimated = compute_cost(0, 0, "claude-3-5-sonnet")
    assert cost == 0.0
    assert estimated is False


def test_pricing_table_has_expected_models():
    """Pricing table includes common Claude models."""
    assert "claude-3-5-sonnet" in PRICING_TABLE
    assert "claude-3-haiku" in PRICING_TABLE
    assert "claude-opus-4" in PRICING_TABLE
