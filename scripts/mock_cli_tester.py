"""Mock data generator for manually verifying the CLI."""

from veritas.core import CostEvent
from veritas.sinks import SQLiteSink
from veritas.utils import utc_now_iso
import random

def generate_mock_data():
    sink = SQLiteSink()
    
    feature = "cli_test_feature"
    base_commit = "abcd123"
    target_commit = "efgh456"

    print(f"Generating 10 'Before' events for commit {base_commit}...")
    for _ in range(10):
        # Base implementation uses around 100 in, 50 out
        e = CostEvent(
            feature=feature,
            model="claude-3-5-sonnet",
            tokens_in=random.randint(90, 110),
            tokens_out=random.randint(40, 60),
            cache_creation_tokens=0,
            cache_read_tokens=0,
            latency_ms=random.uniform(500, 700),
            cost_usd=random.uniform(0.001, 0.003),
            code_version=base_commit,
            timestamp=utc_now_iso(),
            status="ok",
            estimated=True
        )
        sink.emit(e)

    print(f"Generating 10 'After' events for commit {target_commit} (with a massive regression)...")
    for _ in range(10):
        # Target implementation accidentally returns 2x tokens and costs $0.05 per request
        e = CostEvent(
            feature=feature,
            model="claude-3-5-sonnet",
            tokens_in=random.randint(190, 210),
            tokens_out=random.randint(90, 110),
            cache_creation_tokens=0,
            cache_read_tokens=0,
            latency_ms=random.uniform(1000, 1500),
            cost_usd=random.uniform(0.045, 0.055), # Crosses the $0.01 regression threshold
            code_version=target_commit,
            timestamp=utc_now_iso(),
            status="ok",
            estimated=True
        )
        sink.emit(e)

    sink.close()
    print("Done! Run the following command to test:")
    print(f"veritas diff --feature {feature} --from {base_commit} --to {target_commit}")

if __name__ == "__main__":
    generate_mock_data()
