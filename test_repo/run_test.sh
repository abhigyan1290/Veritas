#!/bin/bash
# Mock CI Workflow Simulator

echo "=== 1. Setting up fresh environment ==="
source venv/Scripts/activate

# Install the package directly from GitHub
echo "=== 2. Installing expected version from GitHub ==="
pip install git+https://github.com/abhigyan1290/Veritas.git@main

# Simulate Commit A
echo ""
echo "=== 3. Simulating BASE commit (Commit A) ==="
export GITHUB_SHA="commit_a_123"
python simulate_app.py

# Simulate Commit B
echo ""
echo "=== 4. Simulating TARGET commit (Commit B) ==="
export GITHUB_SHA="commit_b_456"
python simulate_app.py

echo ""
echo "=== 5. Running Veritas Cost Difference CLI ==="
# We expect this to execute and evaluate the difference between
# our two commits. In this simulation, since they cost exactly
# the same ($0.50), it should exit cleanly.
veritas diff --feature "github_ci_test" --from "commit_a_123" --to "commit_b_456"
