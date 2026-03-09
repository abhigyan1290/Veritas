import os
import sys
from dotenv import load_dotenv
from anthropic import Anthropic
from veritas.core import CostEvent
from veritas.sinks import HttpSink
from veritas.pricing import compute_cost
import time
from datetime import datetime, timezone

# Auto-load variables from .env to pick up ANTHROPIC_API_KEY
load_dotenv()

# 1. Setup Data Paths
os.environ["VERITAS_DB_PATH"] = "my_ci_events.db"
COMMIT_HASH = os.environ.get("GITHUB_SHA", "live_test_123")
SCENARIO = os.environ.get("SCENARIO", "BASE")

print(f"--- Running LIVE API Test | Commit: {COMMIT_HASH} | Scenario: {SCENARIO} ---")

# 2. Check for Anthropic Key
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("❌ ERROR: You must set the ANTHROPIC_API_KEY environment variable to run this script.")
    sys.exit(1)

client = Anthropic(api_key=api_key)
# Explicitly leverage HttpSink to emit to the local dashboard with instantaneous flushing
sink = HttpSink(batch_size=1)

try:
    # 3. Define our prompt scenario
    if SCENARIO == "BASE":
        model_name = "claude-3-haiku-20240307"
        prompt = "Hello! Please give me a one sentence summary of the color blue."
    else:
        # In the TARGET scenario, we make the prompt much larger. Since the API key seems restricted to Haiku,
        # we will force a cost regression purely by pumping a massive amount of tokens into the context window.
        model_name = "claude-3-haiku-20240307"
        prompt = "Write a comprehensive 5 paragraph essay on the history of the color blue. Give me as much detail as possible, including its use in ancient times, the renaissance, and modern psychology. Format it beautifully." + (" We need more tokens. " * 500)

    print(f"Sending prompt to Claude: '{prompt[:40]}...' [Model: {model_name}]")
    
    # 4. Make the real API call
    start_time = time.time()
    response = client.messages.create(
        model=model_name,
        max_tokens=1000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    latency = (time.time() - start_time) * 1000

    # 5. Extract specific token counts from response.usage
    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    
    # Safely handle cache fields (Haiku may or may not return them depending on length)
    cache_creation = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0

    # 6. Compute Cost using Veritas
    calculated_cost_tuple = compute_cost(
        model=model_name,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cache_creation_tokens=cache_creation,
        cache_read_tokens=cache_read
    )
    calculated_cost = calculated_cost_tuple[0]

    # 7. Wrap into Veritas CostEvent
    event = CostEvent(
        feature="live_api_call",
        model=model_name,
        code_version=COMMIT_HASH,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cache_creation_tokens=cache_creation,
        cache_read_tokens=cache_read,
        latency_ms=latency,
        cost_usd=calculated_cost,
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    sink.emit(event)
    print(f"✅ Success! Cost logged to Dashboard: ${calculated_cost:.6f} ({tokens_in} in / {tokens_out} out)")

finally:
    sink.flush()
