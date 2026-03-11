"""Tests for utils module."""

import re

import pytest

from veritas.utils import get_current_commit_hash, utc_now_iso


class TestGetCurrentCommitHash:
    """Tests for get_current_commit_hash."""

    def test_returns_hash_when_git_available(self, monkeypatch):
        """Returns commit hash when git succeeds."""
        def mock_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = "a81cd29\n"
                stderr = ""
            return Result()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        assert get_current_commit_hash() == "a81cd29"

    def test_returns_none_when_not_in_repo(self, monkeypatch):
        """Returns None when not in a git repo."""
        def mock_run(*args, **kwargs):
            class Result:
                returncode = 128
                stdout = ""
                stderr = "fatal: not a git repository"
            return Result()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        assert get_current_commit_hash() == "unknown"

    def test_returns_none_when_git_not_found(self, monkeypatch):
        """Returns None when git command not found."""

        def mock_run(*args, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr("veritas.utils.subprocess.run", mock_run)
        assert get_current_commit_hash() == "unknown"


class TestUtcNowIso:
    """Tests for utc_now_iso."""

    def test_returns_valid_iso8601_format(self):
        """Returns a string in ISO 8601 format."""
        s = utc_now_iso()
        # Format: 2026-03-06T19:02:11Z
        pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
        assert re.match(pattern, s), f"Expected ISO8601, got {s}"
