"""Veritas — AI cost attribution and change detection."""

__version__ = "0.1.0.dev0"

from veritas.core import CostEvent, track, set_default_sink, get_default_sink
from veritas.sinks import BaseSink, ConsoleSink, SQLiteSink, HttpSink
from veritas.utils import get_current_commit_hash, utc_now_iso
from veritas.client import Anthropic

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
    "utc_now_iso",
    "Anthropic"
]

# Auto-configure the default sink if environment variables are present
import os
if os.environ.get("VERITAS_API_KEY") and os.environ.get("VERITAS_API_URL"):
    set_default_sink(HttpSink(os.environ["VERITAS_API_URL"], os.environ["VERITAS_API_KEY"]))
elif os.environ.get("VERITAS_DB_PATH"):
    set_default_sink(SQLiteSink(os.environ["VERITAS_DB_PATH"]))
