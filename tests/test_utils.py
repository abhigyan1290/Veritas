import pytest
import os
from unittest.mock import patch

from veritas.utils import get_current_commit_hash

def test_get_current_commit_hash_with_env_mock():
    """Ensure the environment variable completely overrides Git logic."""
    with patch.dict(os.environ, {"VERITAS_MOCK_COMMIT": "mock_abc123"}):
        assert get_current_commit_hash() == "mock_abc123"

@patch("subprocess.run")
def test_get_current_commit_hash_git_success(mock_run):
    """Ensure standard git execution returns the hash."""
    # Ensure env var is specifically disabled for this test
    with patch.dict(os.environ, clear=True):
        mock_run.return_value.stdout = "real_git_sha_456\n"
        assert get_current_commit_hash() == "real_git_sha_456"

@patch("subprocess.run")
def test_get_current_commit_hash_git_failure(mock_run):
    """Ensure graceful degradation if Git fails (e.g., CI missing git)."""
    import subprocess
    with patch.dict(os.environ, clear=True):
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        assert get_current_commit_hash() == "unknown"
