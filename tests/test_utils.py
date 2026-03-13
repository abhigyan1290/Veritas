"""Tests for utils module — git hash resolution, overrides, dirty detection."""

import os
import re
import subprocess

import pytest

from veritas.utils import (
    _check_dirty,
    _is_valid_hash,
    _resolve_via_subprocess,
    get_current_commit_hash,
    reset_commit_cache,
    set_commit_override,
    utc_now_iso,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _reset_all(monkeypatch):
    """Clear both the cache and the override so each test starts fresh."""
    monkeypatch.setattr("veritas.utils._commit_cache", None)
    monkeypatch.setattr("veritas.utils._commit_override", None)
    # Clear env vars that would override git resolution
    monkeypatch.delenv("VERITAS_CODE_VERSION", raising=False)
    monkeypatch.delenv("VERITAS_MOCK_COMMIT", raising=False)


# ─────────────────────────────────────────────────────────────────────────────
# Hash format validation
# ─────────────────────────────────────────────────────────────────────────────

class TestIsValidHash:
    """Tests for _is_valid_hash."""

    def test_valid_7_char_hash(self):
        assert _is_valid_hash("a81cd29") is True

    def test_valid_full_hash(self):
        assert _is_valid_hash("a81cd2943b12e3f456789abcdef0123456789abc") is True

    def test_valid_dirty_hash(self):
        assert _is_valid_hash("a81cd29+dirty") is True

    def test_rejects_too_short(self):
        assert _is_valid_hash("abc") is False

    def test_rejects_uppercase(self):
        assert _is_valid_hash("A81CD29") is False

    def test_rejects_garbage(self):
        assert _is_valid_hash("not-a-hash") is False

    def test_rejects_empty(self):
        assert _is_valid_hash("") is False


# ─────────────────────────────────────────────────────────────────────────────
# Core resolution: subprocess path
# ─────────────────────────────────────────────────────────────────────────────

class TestGetCurrentCommitHash:
    """Tests for get_current_commit_hash."""

    def test_returns_hash_when_git_available(self, monkeypatch):
        """Returns commit hash when git succeeds and working tree is clean."""
        _reset_all(monkeypatch)

        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = "a81cd29\n"
                stderr = ""
            if "rev-parse" in cmd:
                return Result()
            # git diff --quiet HEAD → returncode 0 = clean
            class CleanResult:
                returncode = 0
                stdout = ""
                stderr = ""
            return CleanResult()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        # Disable dotgit fast-path to test subprocess path
        monkeypatch.setattr("veritas.utils._resolve_from_dotgit", lambda: None)
        assert get_current_commit_hash() == "a81cd29"

    def test_returns_unknown_when_not_in_repo(self, monkeypatch):
        """Returns 'unknown' when not in a git repo."""
        _reset_all(monkeypatch)

        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 128
                stdout = ""
                stderr = "fatal: not a git repository"
            return Result()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        monkeypatch.setattr("veritas.utils._resolve_from_dotgit", lambda: None)
        assert get_current_commit_hash() == "unknown"

    def test_returns_unknown_when_git_not_found(self, monkeypatch):
        """Returns 'unknown' when git command not found."""
        _reset_all(monkeypatch)

        def mock_run(cmd, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        monkeypatch.setattr("veritas.utils._resolve_from_dotgit", lambda: None)
        assert get_current_commit_hash() == "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Dirty detection
# ─────────────────────────────────────────────────────────────────────────────

class TestDirtyDetection:
    """Tests for working-tree dirty flag."""

    def test_dirty_flag_appended(self, monkeypatch):
        """Appends +dirty when git diff --quiet returns non-zero."""
        _reset_all(monkeypatch)

        call_count = {"n": 0}

        def mock_run(cmd, **kwargs):
            call_count["n"] += 1
            if "rev-parse" in cmd:
                class Result:
                    returncode = 0
                    stdout = "abc1234\n"
                    stderr = ""
                return Result()
            # git diff --quiet HEAD → returncode 1 = dirty
            class DirtyResult:
                returncode = 1
                stdout = ""
                stderr = ""
            return DirtyResult()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        monkeypatch.setattr("veritas.utils._resolve_from_dotgit", lambda: None)
        assert get_current_commit_hash() == "abc1234+dirty"

    def test_clean_repo_no_dirty_suffix(self, monkeypatch):
        """No +dirty suffix when git diff --quiet returns 0."""
        _reset_all(monkeypatch)

        def mock_run(cmd, **kwargs):
            if "rev-parse" in cmd:
                class Result:
                    returncode = 0
                    stdout = "abc1234\n"
                    stderr = ""
                return Result()
            class CleanResult:
                returncode = 0
                stdout = ""
                stderr = ""
            return CleanResult()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        monkeypatch.setattr("veritas.utils._resolve_from_dotgit", lambda: None)
        assert get_current_commit_hash() == "abc1234"


# ─────────────────────────────────────────────────────────────────────────────
# Environment variable overrides
# ─────────────────────────────────────────────────────────────────────────────

class TestEnvOverrides:
    """Tests for VERITAS_CODE_VERSION and VERITAS_MOCK_COMMIT."""

    def test_veritas_code_version_override(self, monkeypatch):
        """VERITAS_CODE_VERSION takes precedence over git resolution."""
        _reset_all(monkeypatch)
        monkeypatch.setenv("VERITAS_CODE_VERSION", "deadbeef")
        assert get_current_commit_hash() == "deadbeef"

    def test_mock_commit_still_works(self, monkeypatch):
        """VERITAS_MOCK_COMMIT still works for backward compatibility."""
        _reset_all(monkeypatch)
        monkeypatch.setenv("VERITAS_MOCK_COMMIT", "cafebabe")
        assert get_current_commit_hash() == "cafebabe"

    def test_code_version_beats_mock_commit(self, monkeypatch):
        """VERITAS_CODE_VERSION has higher priority than VERITAS_MOCK_COMMIT."""
        _reset_all(monkeypatch)
        monkeypatch.setenv("VERITAS_CODE_VERSION", "winner00")
        monkeypatch.setenv("VERITAS_MOCK_COMMIT", "loser000")
        assert get_current_commit_hash() == "winner00"


# ─────────────────────────────────────────────────────────────────────────────
# Module-level override (via init)
# ─────────────────────────────────────────────────────────────────────────────

class TestCommitOverride:
    """Tests for set_commit_override / module-level override."""

    def test_override_takes_precedence(self, monkeypatch):
        """set_commit_override makes get_current_commit_hash return override."""
        _reset_all(monkeypatch)
        set_commit_override("explicit1")
        assert get_current_commit_hash() == "explicit1"
        # Clean up
        set_commit_override(None)

    def test_override_beats_env_vars(self, monkeypatch):
        """Module override has higher priority than env vars."""
        _reset_all(monkeypatch)
        monkeypatch.setenv("VERITAS_CODE_VERSION", "fromenv01")
        set_commit_override("fromcode1")
        assert get_current_commit_hash() == "fromcode1"
        set_commit_override(None)


# ─────────────────────────────────────────────────────────────────────────────
# Cache behavior
# ─────────────────────────────────────────────────────────────────────────────

class TestCacheBehavior:
    """Tests for caching and reset_commit_cache."""

    def test_caches_result(self, monkeypatch):
        """Second call returns cached result without hitting git again."""
        _reset_all(monkeypatch)
        call_count = {"n": 0}

        def mock_run(cmd, **kwargs):
            call_count["n"] += 1
            if "rev-parse" in cmd:
                class Result:
                    returncode = 0
                    stdout = "abc1234\n"
                    stderr = ""
                return Result()
            class CleanResult:
                returncode = 0
                stdout = ""
                stderr = ""
            return CleanResult()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        monkeypatch.setattr("veritas.utils._resolve_from_dotgit", lambda: None)

        first = get_current_commit_hash()
        subprocess_calls_after_first = call_count["n"]

        second = get_current_commit_hash()
        assert first == second == "abc1234"
        # No extra subprocess calls on second invocation
        assert call_count["n"] == subprocess_calls_after_first

    def test_reset_commit_cache(self, monkeypatch):
        """After reset_commit_cache(), the next call re-resolves from git."""
        _reset_all(monkeypatch)
        call_count = {"n": 0}

        def mock_run(cmd, **kwargs):
            call_count["n"] += 1
            if "rev-parse" in cmd:
                class Result:
                    returncode = 0
                    stdout = f"aaa{call_count['n']:04d}\n"
                    stderr = ""
                return Result()
            class CleanResult:
                returncode = 0
                stdout = ""
                stderr = ""
            return CleanResult()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        monkeypatch.setattr("veritas.utils._resolve_from_dotgit", lambda: None)

        first = get_current_commit_hash()
        assert first.startswith("aaa")

        reset_commit_cache()
        second = get_current_commit_hash()
        # After reset, it should have called subprocess again
        assert first != second


# ─────────────────────────────────────────────────────────────────────────────
# .git/HEAD fast-path
# ─────────────────────────────────────────────────────────────────────────────

class TestDotgitFastPath:
    """Tests for _resolve_from_dotgit fast-path."""

    def test_fast_path_used_when_available(self, monkeypatch, tmp_path):
        """Hash resolved from .git/HEAD without subprocess when available."""
        _reset_all(monkeypatch)

        # Set up a fake .git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        refs_dir = git_dir / "refs" / "heads"
        refs_dir.mkdir(parents=True)
        (refs_dir / "main").write_text("a" * 40 + "\n")

        monkeypatch.chdir(tmp_path)

        from veritas.utils import _resolve_from_dotgit
        result = _resolve_from_dotgit()
        assert result == "a" * 7

    def test_fast_path_detached_head(self, monkeypatch, tmp_path):
        """Detached HEAD: .git/HEAD contains a full hash directly."""
        _reset_all(monkeypatch)

        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        full_hash = "b" * 40
        (git_dir / "HEAD").write_text(full_hash + "\n")

        monkeypatch.chdir(tmp_path)

        from veritas.utils import _resolve_from_dotgit
        result = _resolve_from_dotgit()
        assert result == "b" * 7

    def test_fast_path_returns_none_when_no_git_dir(self, monkeypatch, tmp_path):
        """Returns None when no .git directory exists."""
        monkeypatch.chdir(tmp_path)

        from veritas.utils import _resolve_from_dotgit
        assert _resolve_from_dotgit() is None


# ─────────────────────────────────────────────────────────────────────────────
# Invalid hash handling
# ─────────────────────────────────────────────────────────────────────────────

class TestInvalidHashHandling:
    """Tests for handling garbage git output."""

    def test_invalid_hash_returns_unknown(self, monkeypatch):
        """Garbage subprocess output → returns 'unknown'."""
        _reset_all(monkeypatch)

        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = "NOT-A-VALID-HASH\n"
                stderr = ""
            return Result()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        monkeypatch.setattr("veritas.utils._resolve_from_dotgit", lambda: None)
        assert get_current_commit_hash() == "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# utc_now_iso (unchanged from original)
# ─────────────────────────────────────────────────────────────────────────────

class TestUtcNowIso:
    """Tests for utc_now_iso."""

    def test_returns_valid_iso8601_format(self):
        """Returns a string in ISO 8601 format."""
        s = utc_now_iso()
        # Format: 2026-03-06T19:02:11Z
        pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
        assert re.match(pattern, s), f"Expected ISO8601, got {s}"
