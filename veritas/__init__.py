"""Veritas — AI cost attribution and change detection."""

__version__ = "0.1.0.dev0"

from veritas.core import CostEvent, track, set_default_sink, get_default_sink
from veritas.sinks import BaseSink, ConsoleSink, SQLiteSink, HttpSink
from veritas.utils import get_current_commit_hash
from veritas.client import Anthropic
import os

# Auto-configure the default tracking sink based on Phase 3 Environment Variables
if os.environ.get("VERITAS_API_KEY"):
    set_default_sink(HttpSink())
elif os.environ.get("VERITAS_DB_PATH"):
    set_default_sink(SQLiteSink())

__all__ = [
    "__version__",
    "CostEvent",
    "track",
    "set_default_sink",
    "get_default_sink",
    "BaseSink",
    "ConsoleSink",
    "SQLiteSink",
    "HttpSink",
    "get_current_commit_hash",
    "Anthropic",
]
