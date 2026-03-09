import os
import sys

# 1. Assert we can import it
try:
    from veritas.core import CostEvent
    from veritas.sinks import SQLiteSink
    print("✅ Successfully imported `veritas` from GitHub installation!")
except ImportError as e:
    print(f"❌ Failed to import veritas: {e}")
    sys.exit(1)

# 2. Grab the commit hash from the environment (simulating GitHub Actions)
COMMIT_HASH = os.environ.get("GITHUB_SHA", "local_test_hash")

# 3. Simulate creating some dummy data
print(f"Simulating event ingestion for commit: {COMMIT_HASH}")
sink = SQLiteSink(path="ci_test_events.db")

try:
    for i in range(5):
        event = CostEvent(
            feature="github_ci_test",
            code_version=COMMIT_HASH,
            model="gpt-4",
            timestamp=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            # We'll make it cost $0.50 per request
            cost_usd=0.50,
            tokens_in=1000,
            tokens_out=500,
            cache_creation_tokens=100,
            cache_read_tokens=20,
            latency_ms=1200
        )
        sink.emit(event)
    print("✅ Successfully recorded 5 events to SQLite DB.")
finally:
    sink.close()

print("Test script completed successfully!")
