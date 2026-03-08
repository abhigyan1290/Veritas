"""Tests for @track decorator."""

from unittest.mock import MagicMock

import pytest

from veritas import track
from veritas.core import CostEvent


class InMemorySink:
    """Sink that collects events for testing."""

    def __init__(self):
        self.events: list[CostEvent] = []

    def emit(self, event: CostEvent) -> None:
        self.events.append(event)


class TestTrackDecorator:
    """Tests for the @track decorator."""

    def test_emits_event_on_success(self):
        """Decorator emits event with correct fields when function succeeds."""
        sink = InMemorySink()

        @track(feature="chat_search", sink=sink)
        def call_api():
            # Fake Anthropic-style response
            resp = MagicMock()
            resp.model = "claude-3-5-sonnet-20241022"
            resp.usage = MagicMock()
            resp.usage.input_tokens = 100
            resp.usage.output_tokens = 50
            resp.usage.cache_creation_input_tokens = 10
            resp.usage.cache_read_input_tokens = 20
            return resp

        result = call_api()

        assert result.usage.input_tokens == 100
        assert len(sink.events) == 1
        event = sink.events[0]
        assert event.feature == "chat_search"
        assert event.model == "claude-3-5-sonnet-20241022"
        assert event.tokens_in == 100
        assert event.tokens_out == 50
        assert event.cache_creation_tokens == 10
        assert event.cache_read_tokens == 20
        assert event.status == "ok"
        assert event.latency_ms >= 0
        assert event.cost_usd > 0

    def test_extracts_from_dict_style_response(self):
        """Extractor handles dict-style usage (e.g. OpenAI compatibility)."""
        sink = InMemorySink()

        @track(feature="doc_summary", sink=sink)
        def call_api():
            return {
                "model": "claude-3-haiku",
                "usage": {"input_tokens": 200, "output_tokens": 75, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 15},
            }

        call_api()

        assert len(sink.events) == 1
        event = sink.events[0]
        assert event.model == "claude-3-haiku"
        assert event.tokens_in == 200
        assert event.tokens_out == 75
        assert event.cache_creation_tokens == 5
        assert event.cache_read_tokens == 15

    def test_emits_error_event_and_reraises(self):
        """On exception, emits error event and re-raises."""
        sink = InMemorySink()

        @track(feature="chat", sink=sink)
        def failing_call():
            raise ValueError("API error")

        with pytest.raises(ValueError, match="API error"):
            failing_call()

        assert len(sink.events) == 1
        event = sink.events[0]
        assert event.status == "error"
        assert event.tokens_in == 0
        assert event.tokens_out == 0
        assert event.cost_usd == 0.0

    def test_preserves_function_metadata(self):
        """Decorator preserves wrapped function name and docstring."""
        @track(feature="test")
        def my_tracked_function():
            """My docstring."""
            return {"model": "test", "usage": {"input_tokens": 1, "output_tokens": 1}}

        assert my_tracked_function.__name__ == "my_tracked_function"
        assert my_tracked_function.__doc__ == "My docstring."

    def test_returns_result_unchanged(self):
        """Decorator returns the original function result."""
        sink = InMemorySink()

        @track(feature="test", sink=sink)
        def returns_value():
            return {"model": "x", "usage": {"input_tokens": 1, "output_tokens": 1}, "answer": 42}

        result = returns_value()
        assert result["answer"] == 42
