"""Tests for sink implementations."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from veritas.core import CostEvent
from veritas.sinks import BaseSink, ConsoleSink, HttpSink, SQLiteSink


def _make_event(**overrides) -> CostEvent:
    """Build a CostEvent with defaults."""
    defaults = {
        "feature": "test_feature",
        "model": "claude-3-5-sonnet",
        "tokens_in": 100,
        "tokens_out": 50,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "latency_ms": 200.0,
        "cost_usd": 0.001,
        "code_version": "abc123",
        "timestamp": "2026-03-06T12:00:00Z",
        "status": "ok",
        "estimated": False,
        "tags": {"default": "tag"},
    }
    defaults.update(overrides)
    return CostEvent(**defaults)


class TestConsoleSink:
    """Tests for ConsoleSink."""

    def test_emit_prints_valid_json(self, capsys):
        """ConsoleSink.emit prints valid JSON to stdout."""
        sink = ConsoleSink()
        event = _make_event()

        sink.emit(event)

        captured = capsys.readouterr()
        assert captured.err == ""
        line = captured.out.strip()
        parsed = json.loads(line)
        assert isinstance(parsed, dict)

    def test_emit_includes_all_event_fields(self, capsys):
        """Emitted JSON contains all CostEvent fields."""
        sink = ConsoleSink()
        event = _make_event(
            feature="chat_search",
            model="claude-3-haiku",
            tokens_in=320,
            tokens_out=94,
            cache_creation_tokens=10,
            cache_read_tokens=20,
            latency_ms=612.5,
            cost_usd=0.00234,
            code_version="a81cd29",
            timestamp="2026-03-06T19:02:11Z",
            status="ok",
            estimated=True,
        )

        sink.emit(event)

        captured = capsys.readouterr()
        data = json.loads(captured.out.strip())

        assert data["feature"] == "chat_search"
        assert data["model"] == "claude-3-haiku"
        assert data["tokens_in"] == 320
        assert data["tokens_out"] == 94
        assert data["cache_creation_tokens"] == 10
        assert data["cache_read_tokens"] == 20
        assert data["latency_ms"] == 612.5
        assert data["cost_usd"] == 0.00234
        assert data["code_version"] == "a81cd29"
        assert data["timestamp"] == "2026-03-06T19:02:11Z"
        assert data["status"] == "ok"
        assert data["estimated"] is True

    def test_emit_multiple_events(self, capsys):
        """Multiple emits produce multiple JSON lines."""
        sink = ConsoleSink()
        event1 = _make_event(feature="a")
        event2 = _make_event(feature="b")

        sink.emit(event1)
        sink.emit(event2)

        captured = capsys.readouterr()
        lines = [line for line in captured.out.strip().splitlines() if line]

        assert len(lines) == 2
        assert json.loads(lines[0])["feature"] == "a"
        assert json.loads(lines[1])["feature"] == "b"

    def test_emit_error_status_event(self, capsys):
        """Events with status=error are emitted correctly."""
        sink = ConsoleSink()
        event = _make_event(status="error", tokens_in=0, tokens_out=0, cost_usd=0.0)

        sink.emit(event)

        captured = capsys.readouterr()
        data = json.loads(captured.out.strip())

        assert data["status"] == "error"
        assert data["tokens_in"] == 0
        assert data["tokens_out"] == 0
        assert data["cost_usd"] == 0.0


class TestSQLiteSink:
    """Tests for SQLiteSink."""

    def test_emit_stores_event(self):
        """SQLiteSink.emit inserts a row with correct values."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            sink = SQLiteSink(path)
            event = _make_event(
                feature="chat_search",
                model="claude-3-5-sonnet",
                tokens_in=320,
                tokens_out=94,
                latency_ms=612.5,
                cost_usd=0.0105,
                code_version="a81cd29",
                timestamp="2026-03-06T19:02:11Z",
                status="ok",
                estimated=True,
                tags={"doc_type": "pdf", "pages": "100"},
            )
            sink.emit(event)
            sink.close()

            conn = sqlite3.connect(path)
            row = conn.execute("SELECT * FROM events").fetchone()
            conn.close()

            assert row is not None
            # row: (id, feature, model, tokens_in, tokens_out, cache_creation_tokens, cache_read_tokens, latency_ms, cost_usd,
            #       code_version, timestamp, status, estimated)
            assert row[1] == "chat_search"
            assert row[2] == "claude-3-5-sonnet"
            assert row[3] == 320
            assert row[4] == 94
            assert row[5] == 0
            assert row[6] == 0
            assert row[7] == 612.5
            assert row[8] == 0.0105
            assert row[9] == "a81cd29"
            assert row[10] == "2026-03-06T19:02:11Z"
            assert row[11] == "ok"
            assert row[12] == 1  # estimated stored as 1
            assert json.loads(row[13]) == {"doc_type": "pdf", "pages": "100"}
        finally:
            Path(path).unlink(missing_ok=True)

    def test_emit_multiple_events(self):
        """Multiple emits create multiple rows."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            sink = SQLiteSink(path)
            sink.emit(_make_event(feature="a"))
            sink.emit(_make_event(feature="b"))
            sink.emit(_make_event(feature="c"))
            sink.close()

            conn = sqlite3.connect(path)
            rows = conn.execute("SELECT feature FROM events ORDER BY id").fetchall()
            conn.close()

            assert len(rows) == 3
            assert [r[0] for r in rows] == ["a", "b", "c"]
        finally:
            Path(path).unlink(missing_ok=True)

    def test_emit_stores_null_code_version(self):
        """code_version can be NULL when not in a git repo."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            sink = SQLiteSink(path)
            event = _make_event(code_version=None)
            sink.emit(event)
            sink.close()

            conn = sqlite3.connect(path)
            row = conn.execute("SELECT code_version FROM events").fetchone()
            conn.close()

            assert row is not None
            assert row[0] is None
        finally:
            Path(path).unlink(missing_ok=True)

    def test_emit_error_status_event(self):
        """Events with status=error are stored correctly."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            sink = SQLiteSink(path)
            event = _make_event(status="error", tokens_in=0, tokens_out=0, cost_usd=0.0)
            sink.emit(event)
            sink.close()

            conn = sqlite3.connect(path)
            row = conn.execute("SELECT status, tokens_in, tokens_out, cost_usd FROM events").fetchone()
            conn.close()

            assert row == ("error", 0, 0, 0.0)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_in_memory_db_works(self):
        """SQLiteSink works with :memory: for isolated tests."""
        sink = SQLiteSink(":memory:")
        sink.emit(_make_event(feature="in_memory"))
        # No file to clean up; connection holds the data
        assert sink._conn is not None

    def test_sqlite_sink_is_base_sink(self):
        """SQLiteSink is a subclass of BaseSink."""
        assert issubclass(SQLiteSink, BaseSink)


class TestUnknownVersionWarning:
    """Sinks must warn when code_version is 'unknown' so operators notice misconfiguration."""

    def test_sqlite_sink_warns_on_unknown_code_version(self, caplog):
        """SQLiteSink logs a warning when emitting an event with code_version='unknown'."""
        import logging
        sink = SQLiteSink(":memory:")
        event = _make_event(code_version="unknown")
        with caplog.at_level(logging.WARNING, logger="veritas"):
            sink.emit(event)
        assert any("unknown" in r.message and "VERITAS_CODE_VERSION" in r.message
                   for r in caplog.records), "Expected warning mentioning unknown and VERITAS_CODE_VERSION"

    def test_console_sink_warns_on_unknown_code_version(self, caplog):
        """ConsoleSink logs a warning when emitting an event with code_version='unknown'."""
        import logging
        sink = ConsoleSink()
        event = _make_event(code_version="unknown")
        with caplog.at_level(logging.WARNING, logger="veritas"):
            sink.emit(event)
        assert any("unknown" in r.message and "VERITAS_CODE_VERSION" in r.message
                   for r in caplog.records)

    def test_no_warning_for_known_code_version(self, caplog):
        """No warning emitted when code_version is a real git hash."""
        import logging
        sink = SQLiteSink(":memory:")
        event = _make_event(code_version="abc123456789")
        with caplog.at_level(logging.WARNING, logger="veritas"):
            sink.emit(event)
        assert not any("VERITAS_CODE_VERSION" in r.message for r in caplog.records)


class TestHttpSinkDropLogging:
    """HttpSink must log a warning when the queue is full and events are dropped,
    so operators know they're losing attribution data (not just silently missing it)."""

    def test_logs_warning_when_queue_full(self, caplog):
        """Emitting to a full queue logs a WARNING instead of silently dropping."""
        import logging
        import unittest.mock as mock

        # Patch requests.Session so no real HTTP calls are made
        with mock.patch("veritas.sinks.requests") as mock_requests:
            mock_requests.Session.return_value = mock.MagicMock()
            sink = HttpSink(endpoint_url="http://fake", api_key="test-key")
            # Fill the queue to capacity
            sink._queue.maxsize = 3
            for _ in range(3):
                sink._queue.put_nowait({"dummy": True})

            event = _make_event(feature="overflow_feature")
            with caplog.at_level(logging.WARNING, logger="veritas"):
                sink.emit(event)

        assert any(
            "dropped" in r.message.lower() or "overflow_feature" in r.message
            for r in caplog.records
        ), f"Expected drop warning, got: {[r.message for r in caplog.records]}"

    def test_no_warning_when_queue_has_space(self, caplog):
        """No warning when the queue accepts the event normally."""
        import logging
        import unittest.mock as mock

        with mock.patch("veritas.sinks.requests") as mock_requests:
            mock_requests.Session.return_value = mock.MagicMock()
            sink = HttpSink(endpoint_url="http://fake", api_key="test-key")
            event = _make_event()
            with caplog.at_level(logging.WARNING, logger="veritas"):
                sink.emit(event)

        assert not any("dropped" in r.message.lower() for r in caplog.records)


class TestBaseSink:
    """Tests for sink interface."""

    def test_console_sink_is_base_sink(self):
        """ConsoleSink is a subclass of BaseSink."""
        assert issubclass(ConsoleSink, BaseSink)
