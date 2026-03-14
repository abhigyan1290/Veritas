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
    """Tests for _is_valid_hash — minimum 12 hex chars to reduce collision risk."""

    def test_valid_12_char_hash(self):
        assert _is_valid_hash("a81cd29b3e4f") is True

    def test_valid_full_hash(self):
        assert _is_valid_hash("a81cd2943b12e3f456789abcdef0123456789abc") is True

    def test_valid_12_char_dirty_hash(self):
        assert _is_valid_hash("a81cd29b3e4f+dirty") is True

    def test_rejects_7_char_hash(self):
        """7-char hash no longer valid — minimum is 12 to reduce collision risk."""
        assert _is_valid_hash("a81cd29") is False

    def test_rejects_11_char_hash(self):
        """One below minimum boundary."""
        assert _is_valid_hash("a81cd29b3e4") is False

    def test_rejects_too_short(self):
        assert _is_valid_hash("abc") is False

    def test_rejects_uppercase(self):
        assert _is_valid_hash("A81CD29B3E4F") is False

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
                stdout = "a81cd29b3e4f\n"
                stderr = ""
            if "rev-parse" in cmd:
                return Result()
            class CleanResult:
                returncode = 0
                stdout = ""
                stderr = ""
            return CleanResult()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        # Disable dotgit fast-path to test subprocess path
        monkeypatch.setattr("veritas.utils._resolve_from_dotgit", lambda: None)
        assert get_current_commit_hash() == "a81cd29b3e4f"

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
        """Appends +dirty when git status --porcelain has output."""
        _reset_all(monkeypatch)

        def mock_run(cmd, **kwargs):
            if "rev-parse" in cmd:
                class Result:
                    returncode = 0
                    stdout = "abc123456789\n"
                    stderr = ""
                return Result()
            # git status --porcelain → non-empty stdout = dirty
            class DirtyResult:
                returncode = 0
                stdout = "?? new_file.py\n"
                stderr = ""
            return DirtyResult()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        monkeypatch.setattr("veritas.utils._resolve_from_dotgit", lambda: None)
        assert get_current_commit_hash() == "abc123456789+dirty"

    def test_clean_repo_no_dirty_suffix(self, monkeypatch):
        """No +dirty suffix when git status --porcelain has no output."""
        _reset_all(monkeypatch)

        def mock_run(cmd, **kwargs):
            if "rev-parse" in cmd:
                class Result:
                    returncode = 0
                    stdout = "abc123456789\n"
                    stderr = ""
                return Result()
            class CleanResult:
                returncode = 0
                stdout = ""
                stderr = ""
            return CleanResult()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        monkeypatch.setattr("veritas.utils._resolve_from_dotgit", lambda: None)
        assert get_current_commit_hash() == "abc123456789"


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
                    stdout = "abc123456789\n"
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
        assert first == second == "abc123456789"
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
                    stdout = f"aaa{call_count['n']:09d}\n"  # 12 chars total
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
# Hash length — must be 12 chars from all resolution paths
# ─────────────────────────────────────────────────────────────────────────────

class TestHashLength:
    """Resolved hashes must be 12 chars (not 7) to reduce collision risk on large repos."""

    def test_subprocess_returns_12_char_hash(self, monkeypatch):
        """git rev-parse --short must use 12, not 7."""
        _reset_all(monkeypatch)

        def mock_run(cmd, **kwargs):
            if "rev-parse" in cmd:
                assert "--short=12" in cmd, f"Expected --short=12 in {cmd}"
                class Result:
                    returncode = 0
                    stdout = "abc123456789\n"
                    stderr = ""
                return Result()
            class CleanResult:
                returncode = 0
                stdout = ""
                stderr = ""
            return CleanResult()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        monkeypatch.setattr("veritas.utils._resolve_from_dotgit", lambda: None)
        result = get_current_commit_hash()
        assert result == "abc123456789"
        assert len(result) == 12

    def test_fast_path_returns_12_char_hash(self, monkeypatch, tmp_path):
        """Fast-path must truncate to 12, not 7."""
        _reset_all(monkeypatch)

        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        refs_dir = git_dir / "refs" / "heads"
        refs_dir.mkdir(parents=True)
        (refs_dir / "main").write_text("a" * 40 + "\n")

        monkeypatch.chdir(tmp_path)
        from veritas.utils import _resolve_from_dotgit
        result = _resolve_from_dotgit()
        assert result is not None
        assert len(result) == 12, f"Expected 12 chars, got {len(result)}: {result!r}"

    def test_packed_refs_fast_path_returns_12_char_hash(self, monkeypatch, tmp_path):
        """packed-refs fast-path also returns 12 chars."""
        _reset_all(monkeypatch)

        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        (git_dir / "packed-refs").write_text(
            "# pack-refs\n" + "b" * 40 + " refs/heads/main\n"
        )

        monkeypatch.chdir(tmp_path)
        from veritas.utils import _resolve_from_dotgit
        result = _resolve_from_dotgit()
        assert result is not None
        assert len(result) == 12


# ─────────────────────────────────────────────────────────────────────────────
# Dirty detection — git status --porcelain (replaces git diff --quiet HEAD)
# ─────────────────────────────────────────────────────────────────────────────

class TestDirtyDetectionV2:
    """_check_dirty must use git status --porcelain to catch untracked files and
    handle unborn HEAD cleanly."""

    def test_check_dirty_detects_untracked_files(self, monkeypatch):
        """Untracked (unstaged) files must be detected as dirty.
        'git diff --quiet HEAD' misses these; 'git status --porcelain' catches them.
        """
        def mock_run(cmd, **kwargs):
            assert "status" in cmd, "Must call git status, not git diff"
            class Result:
                returncode = 0
                stdout = "?? new_file.py\n"
                stderr = ""
            return Result()
        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        assert _check_dirty() is True

    def test_check_dirty_clean_on_empty_status_output(self, monkeypatch):
        """Empty git status output → clean working tree."""
        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = ""
                stderr = ""
            return Result()
        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        assert _check_dirty() is False

    def test_check_dirty_unborn_head_is_not_dirty(self, monkeypatch):
        """Unborn HEAD (empty repo, no commits yet): git status exits 0 with no output.
        Old code used 'git diff HEAD' which returns exit 128 → wrongly marked as dirty.
        """
        def mock_run(cmd, **kwargs):
            # git status --porcelain on a brand-new repo with no files returns 0 + empty
            class Result:
                returncode = 0
                stdout = ""
                stderr = ""
            return Result()
        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        assert _check_dirty() is False

    def test_check_dirty_detects_modified_tracked_files(self, monkeypatch):
        """Modified tracked files still detected (regression guard for existing behavior)."""
        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = " M veritas/utils.py\n"
                stderr = ""
            return Result()
        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        assert _check_dirty() is True

    def test_check_dirty_detects_staged_changes(self, monkeypatch):
        """Staged but uncommitted changes are dirty."""
        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = "M  veritas/utils.py\n"
                stderr = ""
            return Result()
        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        assert _check_dirty() is True

    def test_check_dirty_returns_false_on_subprocess_error(self, monkeypatch):
        """If git is not installed, assume clean (never crash the host app)."""
        def mock_run(cmd, **kwargs):
            raise FileNotFoundError()
        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        assert _check_dirty() is False


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
        assert result == "a" * 12

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
        assert result == "b" * 12

    def test_fast_path_reads_packed_refs(self, monkeypatch, tmp_path):
        """Fast-path resolves hash from .git/packed-refs when the loose ref file is absent.

        This is the common case after 'git gc' or in shallow CI clones where
        refs are packed and no loose ref files exist under refs/heads/.
        """
        _reset_all(monkeypatch)

        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        # Deliberately NO loose ref file — only packed-refs
        packed = (
            "# pack-refs with: peeled fully-peeled sorted\n"
            + "d" * 40 + " refs/heads/main\n"
            + "e" * 40 + " refs/heads/other\n"
        )
        (git_dir / "packed-refs").write_text(packed)

        monkeypatch.chdir(tmp_path)

        from veritas.utils import _resolve_from_dotgit
        result = _resolve_from_dotgit()
        assert result == "d" * 12

    def test_fast_path_loose_ref_beats_packed_refs(self, monkeypatch, tmp_path):
        """Loose ref file takes precedence over packed-refs (git's own behaviour)."""
        _reset_all(monkeypatch)

        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

        # Both loose and packed refs exist — loose wins
        refs_dir = git_dir / "refs" / "heads"
        refs_dir.mkdir(parents=True)
        (refs_dir / "main").write_text("a" * 40 + "\n")

        packed = (
            "# pack-refs with: peeled\n"
            + "b" * 40 + " refs/heads/main\n"  # different hash in packed
        )
        (git_dir / "packed-refs").write_text(packed)

        monkeypatch.chdir(tmp_path)

        from veritas.utils import _resolve_from_dotgit
        result = _resolve_from_dotgit()
        assert result == "a" * 12  # loose ref wins, not "b" * 12

    def test_fast_path_packed_refs_missing_ref_returns_none(self, monkeypatch, tmp_path):
        """Returns None if the ref isn't in packed-refs either (fallback to subprocess)."""
        _reset_all(monkeypatch)

        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        # packed-refs exists but doesn't contain refs/heads/main
        (git_dir / "packed-refs").write_text(
            "# pack-refs with: peeled\n"
            + "c" * 40 + " refs/heads/other\n"
        )

        monkeypatch.chdir(tmp_path)

        from veritas.utils import _resolve_from_dotgit
        assert _resolve_from_dotgit() is None

    def test_fast_path_returns_none_when_no_git_dir(self, monkeypatch, tmp_path):
        """Returns None when no .git directory exists."""
        monkeypatch.chdir(tmp_path)

        from veritas.utils import _resolve_from_dotgit
        assert _resolve_from_dotgit() is None


# ─────────────────────────────────────────────────────────────────────────────
# Env var format warnings
# ─────────────────────────────────────────────────────────────────────────────

class TestEnvVarFormatWarning:
    """When VERITAS_CODE_VERSION is set to a non-hash value (e.g. a tag or slug),
    the value is still used (user intent) but a WARNING is logged so operators
    know events won't align with git hash queries."""

    def test_warns_when_env_var_is_not_a_git_hash(self, monkeypatch, caplog):
        """Non-hex env var value logs a WARNING but is still returned."""
        import logging
        _reset_all(monkeypatch)
        monkeypatch.setenv("VERITAS_CODE_VERSION", "v1.2.3-production")
        with caplog.at_level(logging.WARNING, logger="veritas"):
            result = get_current_commit_hash()
        assert result == "v1.2.3-production"
        assert any("v1.2.3-production" in r.message for r in caplog.records), \
            "Expected warning mentioning the non-hash value"

    def test_warns_for_plain_slug(self, monkeypatch, caplog):
        """Common mistake: setting env var to a deploy slug like 'production'."""
        import logging
        _reset_all(monkeypatch)
        monkeypatch.setenv("VERITAS_CODE_VERSION", "production")
        with caplog.at_level(logging.WARNING, logger="veritas"):
            result = get_current_commit_hash()
        assert result == "production"
        assert any("production" in r.message for r in caplog.records)

    def test_no_warning_for_valid_short_hash(self, monkeypatch, caplog):
        """Valid hex hash in env var → no warning."""
        import logging
        _reset_all(monkeypatch)
        monkeypatch.setenv("VERITAS_CODE_VERSION", "abc1234def56")
        with caplog.at_level(logging.WARNING, logger="veritas"):
            get_current_commit_hash()
        assert not any("VERITAS_CODE_VERSION" in r.message for r in caplog.records)

    def test_no_warning_for_valid_full_hash(self, monkeypatch, caplog):
        """Full 40-char hex hash → no warning."""
        import logging
        _reset_all(monkeypatch)
        monkeypatch.setenv("VERITAS_CODE_VERSION", "a" * 40)
        with caplog.at_level(logging.WARNING, logger="veritas"):
            get_current_commit_hash()
        assert not any("VERITAS_CODE_VERSION" in r.message for r in caplog.records)


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
