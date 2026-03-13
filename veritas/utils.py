"""Environment detection, git version resolution, timestamps."""

import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("veritas")

# Regex for a valid short/full git hash, optionally with +dirty suffix.
_HASH_RE = re.compile(r"^[0-9a-f]{7,40}(\+dirty)?$")

# Module-level cache: commit hash is resolved once per process lifetime.
# The hash cannot change while the process is running, so repeated subprocess
# calls are wasteful. None means "not yet resolved".
_commit_cache: str | None = None

# Module-level override set via veritas.init(code_version=...).
_commit_override: str | None = None


def _is_valid_hash(value: str) -> bool:
    """Check whether *value* looks like a plausible git hash (with optional +dirty)."""
    return bool(_HASH_RE.match(value))


def _resolve_from_dotgit() -> str | None:
    """Try to read the commit hash directly from .git/HEAD + ref files.

    This avoids spawning a subprocess for the common case (a normal checkout).
    Returns the 7-char shortened hash, or None if it cannot be resolved this way.
    """
    try:
        # Walk up from cwd looking for a .git directory
        cwd = Path.cwd()
        search = cwd
        git_dir: Path | None = None
        for _ in range(10):  # limit depth to avoid infinite loops
            candidate = search / ".git"
            if candidate.is_dir():
                git_dir = candidate
                break
            if candidate.is_file():
                # Worktree: .git is a file containing "gitdir: <path>"
                text = candidate.read_text().strip()
                if text.startswith("gitdir:"):
                    git_dir = Path(text.split(":", 1)[1].strip())
                    if not git_dir.is_absolute():
                        git_dir = (search / git_dir).resolve()
                break
            parent = search.parent
            if parent == search:
                break
            search = parent

        if git_dir is None:
            return None

        head_file = git_dir / "HEAD"
        if not head_file.is_file():
            return None

        head_content = head_file.read_text().strip()

        if head_content.startswith("ref:"):
            # Symbolic ref — resolve it
            ref_path = git_dir / head_content.split(":", 1)[1].strip()
            if not ref_path.is_file():
                return None  # packed refs — fall back to subprocess
            full_hash = ref_path.read_text().strip()
        else:
            # Detached HEAD — content is the full hash
            full_hash = head_content

        if len(full_hash) >= 7 and all(c in "0123456789abcdef" for c in full_hash):
            return full_hash[:7]

        return None
    except (OSError, ValueError):
        return None


def _check_dirty() -> bool:
    """Return True if the working tree has uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "diff", "--quiet", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # returncode 0 = clean, 1 = dirty
        return result.returncode != 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False  # if we can't tell, assume clean


def _resolve_via_subprocess() -> str | None:
    """Resolve the commit hash by shelling out to git. Returns 7-char hash or None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def get_current_commit_hash() -> str:
    """Return the current git commit hash, or 'unknown' if not in a repo.

    Resolution priority:
      1. Module-level override set via ``veritas.init(code_version=...)``.
      2. ``VERITAS_CODE_VERSION`` environment variable (production override).
      3. ``VERITAS_MOCK_COMMIT`` environment variable (deprecated alias).
      4. Cached value from a previous call.
      5. Fast-path: read ``.git/HEAD`` directly (no subprocess).
      6. Fallback: ``git rev-parse --short=7 HEAD`` subprocess.

    If the working tree has uncommitted changes, ``+dirty`` is appended
    (e.g. ``abc1234+dirty``).

    The result is cached for the lifetime of the process — git is only
    invoked once.
    """
    global _commit_cache

    # 1. Module-level override (set via veritas.init)
    if _commit_override is not None:
        return _commit_override

    # 2-3. Environment variable overrides (checked every call for test flexibility)
    env_override = os.environ.get("VERITAS_CODE_VERSION") or os.environ.get("VERITAS_MOCK_COMMIT")
    if env_override:
        return env_override

    # 4. Return cached value if already resolved
    if _commit_cache is not None:
        return _commit_cache

    # 5-6. Resolve: try fast path first, fall back to subprocess
    short_hash = _resolve_from_dotgit() or _resolve_via_subprocess()

    if short_hash and _is_valid_hash(short_hash):
        # Check for dirty working tree
        if _check_dirty():
            _commit_cache = f"{short_hash}+dirty"
        else:
            _commit_cache = short_hash
    else:
        if short_hash:
            logger.warning(
                "veritas: git returned unexpected hash format %r, using 'unknown'",
                short_hash,
            )
        _commit_cache = "unknown"

    return _commit_cache


def reset_commit_cache() -> None:
    """Clear the cached commit hash.

    The next call to ``get_current_commit_hash()`` will re-resolve from git.
    Useful for long-running servers that hot-reload code, and for tests.
    """
    global _commit_cache
    _commit_cache = None


def set_commit_override(version: str | None) -> None:
    """Set (or clear) a module-level commit hash override.

    When set, ``get_current_commit_hash()`` always returns this value,
    bypassing git resolution entirely.  Called internally by
    ``veritas.init(code_version=...)``.
    """
    global _commit_override
    _commit_override = version


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
