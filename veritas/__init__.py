"""Veritas — AI cost attribution and change detection."""

__version__ = "0.1.0.dev0"

from veritas.core import CostEvent, track, set_default_sink
from veritas.sinks import BaseSink, ConsoleSink, SQLiteSink
from veritas.utils import get_git_commit_hash, utc_now_iso

__all__ = [
    "__version__",
    "CostEvent",
    "track",
    "set_default_sink",
    "BaseSink",
    "ConsoleSink",
    "SQLiteSink",
    "get_git_commit_hash",
    "utc_now_iso",
]
