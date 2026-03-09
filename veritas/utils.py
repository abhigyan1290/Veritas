import os
import subprocess

def get_current_commit_hash() -> str:
    """
    Safely extract the current Git commit hash.
    
    1. Checks for a VERITAS_MOCK_COMMIT environment variable (used for Demos/CI).
    2. Falls back to executing `git rev-parse HEAD`.
    3. Returns 'unknown' if git fails or is not installed, preventing SDK crashes.
    """
    mock_commit = os.environ.get("VERITAS_MOCK_COMMIT")
    if mock_commit:
        return mock_commit
        
    try:
        # Run git rev-parse HEAD, swallow stderr so we don't spam the developer's console
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # CalledProcessError means git exited non-zero (e.g. not a repo)
        # FileNotFoundError means git is not installed on the system
        return "unknown"
