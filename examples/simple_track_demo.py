"""Minimal example: @track decorator with a fake Claude-style response.

Run from project root:
    python examples/simple_track_demo.py

No API key required — uses a fake response. You'll see a JSON cost event on stdout.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veritas import track


# Fake response mimicking Anthropic SDK
class FakeUsage:
    input_tokens = 150
    output_tokens = 45


class FakeResponse:
    model = "claude-3-5-sonnet-20241022"
    usage = FakeUsage()


@track(feature="chat_search")
def call_claude(prompt: str):
    """Simulated Claude API call."""
    # In real usage: return anthropic.messages.create(...)
    return FakeResponse()


if __name__ == "__main__":
    result = call_claude("Summarize this document.")
    print(f"# Response model: {result.model}")
    print(f"# Tokens: {result.usage.input_tokens} in, {result.usage.output_tokens} out")
