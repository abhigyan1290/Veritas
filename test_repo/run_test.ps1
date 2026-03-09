# Mock CI Workflow Simulator (PowerShell)

Write-Host "=== 1. Setting up fresh environment ==="
# Activate the virtual environment
& .\venv\Scripts\Activate.ps1

# Install the package directly from GitHub
Write-Host "=== 2. Installing expected version from GitHub ==="
pip install git+https://github.com/abhigyan1290/Veritas.git@main

# Simulate Commit A
Write-Host ""
Write-Host "=== 3. Simulating BASE commit (Commit A) ==="
$env:GITHUB_SHA="commit_a_123"
python simulate_app.py

# Simulate Commit B
Write-Host ""
Write-Host "=== 4. Simulating TARGET commit (Commit B) ==="
$env:GITHUB_SHA="commit_b_456"
python simulate_app.py

Write-Host ""
Write-Host "=== 5. Running Veritas Cost Difference CLI ==="
# We expect this to execute and evaluate the difference between
# our two commits. In this simulation, since they cost exactly
# the same ($0.50), it should exit cleanly.
$env:VERITAS_DB_PATH="ci_test_events.db"
veritas diff --feature "github_ci_test" --from "commit_a_123" --to "commit_b_456"
