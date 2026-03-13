"""Tests for CostEvent and to_dict serialization."""

import pytest  # pyright: ignore[reportMissingImports]

from veritas.core import CostEvent


def test_cost_event_creation():
    """CostEvent can be created with required fields."""
    event = CostEvent(
        feature="chat_search",
        model="claude-opus-4",
        tokens_in=320,
        tokens_out=94,
        cache_creation_tokens=100,
        cache_read_tokens=50,
        latency_ms=612.0,
        cost_usd=0.00102,
        code_version="a81cd29",
        timestamp="2026-03-06T19:02:11Z",
        tags={"tenant": "acme"},
    )
    assert event.feature == "chat_search"
    assert event.model == "claude-opus-4"
    assert event.tokens_in == 320
    assert event.tokens_out == 94
    assert event.cache_creation_tokens == 100
    assert event.cache_read_tokens == 50
    assert event.status == "ok"
    assert event.estimated is False
    assert event.tags == {"tenant": "acme"}


def test_cost_event_to_dict():
    """to_dict produces a complete, JSON-serializable dict."""
    event = CostEvent(
        feature="test",
        model="claude-opus-4",
        tokens_in=100,
        tokens_out=50,
        cache_creation_tokens=0,
        cache_read_tokens=10,
        latency_ms=200.0,
        cost_usd=0.001,
        code_version=None,
        timestamp="2026-03-06T12:00:00Z",
        status="ok",
        estimated=True,
        tags={"env": "prod"},
    )
    d = event.to_dict()
    assert d["feature"] == "test"
    assert d["model"] == "claude-opus-4"
    assert d["tokens_in"] == 100
    assert d["tokens_out"] == 50
    assert d["cache_creation_tokens"] == 0
    assert d["cache_read_tokens"] == 10
    assert d["latency_ms"] == 200.0
    assert d["cost_usd"] == 0.001
    assert d["code_version"] is None
    assert d["timestamp"] == "2026-03-06T12:00:00Z"
    assert d["status"] == "ok"
    assert d["estimated"] is True
    assert d["tags"] == {"env": "prod"}
    assert set(d.keys()) == {
        "feature",
        "model",
        "tokens_in",
        "tokens_out",
        "cache_creation_tokens",
        "cache_read_tokens",
        "latency_ms",
        "cost_usd",
        "code_version",
        "timestamp",
        "status",
        "estimated",
        "tags",
    }


def test_cost_event_error_status():
    """CostEvent supports status='error' for failed calls."""
    event = CostEvent(
        feature="chat",
        model="claude-opus-4",
        tokens_in=0,
        tokens_out=0,
        cache_creation_tokens=0,
        cache_read_tokens=0,
        latency_ms=50.0,
        cost_usd=0.0,
        code_version="abc123",
        timestamp="2026-03-06T12:00:00Z",
        status="error",
    )
    assert event.status == "error"
    assert event.to_dict()["status"] == "error"
