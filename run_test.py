import subprocess
import json
res = subprocess.run(['.venv/Scripts/pytest', 'tests/test_tenancy.py', '--tb=short'], capture_output=True, text=True)
with open("test_out.json", "w", encoding="utf-8") as f:
    json.dump({"out": res.stdout, "err": res.stderr}, f)
