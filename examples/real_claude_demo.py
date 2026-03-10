"""Real Claude API example with @track.

1. Copy .env.example to .env and add your key:
       ANTHROPIC_API_KEY=sk-ant-...

2. Install the examples extra:
       pip install -e ".[examples]"

3. Run from project root:
       python examples/real_claude_demo.py

The script loads the key from .env (or from the ANTHROPIC_API_KEY env var).
Cost event is printed as JSON to stdout.
"""

import os
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_env():
    """Load .env from project root into os.environ (no extra deps)."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)


_load_env()

# After loading .env, import veritas and anthropic
from veritas import track

try:
    import anthropic
except ImportError:
    print("Run: pip install -e \".[examples]\"")
    sys.exit(1)


def get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print(
            "Set ANTHROPIC_API_KEY:\n"
            "  - Create a .env file (copy .env.example) and add:\n"
            "    ANTHROPIC_API_KEY=sk-ant-...\n"
            "  - Or in the shell: set ANTHROPIC_API_KEY=sk-ant-..."
        )
        sys.exit(1)
    return key


@track(feature="real_demo")
def call_claude(prompt: str, api_key: str):
    """One real Claude API call."""
    client = anthropic.Anthropic(api_key=api_key)
    return client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )


if __name__ == "__main__":
    api_key = get_api_key()
    prompt = "Say hello in one short sentence."
    print("# Calling Claude (cost event appears above or below)...")
    result = call_claude(prompt, api_key)
    text = result.content[0].text if result.content else ""
    print(f"# Response: {text}")
    print(f"# Model: {result.model}")
    print(f"# Tokens: {result.usage.input_tokens} in, {result.usage.output_tokens} out")
