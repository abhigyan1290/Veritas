"""Environment detection, git version resolution, timestamps."""

import subprocess
import os
from datetime import datetime, timezone

# Module-level cache: commit hash is resolved once per process lifetime.
# The hash cannot change while the process is running, so repeated subprocess
# calls are wasteful. None means "not yet resolved".
_commit_cache: str | None = None


def get_current_commit_hash() -> str:
    """
    Return the current git commit hash, or 'unknown' if not in a repo or git unavailable.
    Supports a VERITAS_MOCK_COMMIT environment variable override for UI demonstrations.

    The result is cached for the lifetime of the process — git is only invoked once.
    """
    global _commit_cache

    # Always honour the mock override (env var can change between calls in tests)
    mock_commit = os.environ.get("VERITAS_MOCK_COMMIT")
    if mock_commit:
        return mock_commit

    # Return cached value if already resolved
    if _commit_cache is not None:
        return _commit_cache

    # First call: shell out to git and cache the result
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            _commit_cache = result.stdout.strip()
        else:
            _commit_cache = "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # FileNotFoundError means git is not installed on the system
        _commit_cache = "unknown"

    return _commit_cache


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
