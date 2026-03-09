# run_real_test.ps1

Write-Host "Installing Veritas from Local Project to test Phase 3 changes..."
pip install -e C:\Users\abhig\project_test
pip install anthropic python-dotenv

# 1. Simulate the BASE commit
Write-Host ""
Write-Host "--- Running Baseline Simulation against Claude API ---"
$env:GITHUB_SHA="111aaaa"
$env:SCENARIO="BASE"
# Make sure your ANTHROPIC_API_KEY is active!
python real_api_test.py

# 2. Simulate the TARGET commit
Write-Host ""
Write-Host "--- Running Target Simulation against Claude API ---"
$env:GITHUB_SHA="222bbbb"
$env:SCENARIO="TARGET"
python real_api_test.py

# 3. VERIFY!
Write-Host ""
Write-Host "✅ Done! Refresh http://localhost:8000 to see both API calls on the dashboard."
