$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

Write-Host "Installing Python deps if needed..."
python -m pip install -r requirements.txt
python -c "from app.agent_browser import bootstrap; import json; print(json.dumps(bootstrap(), ensure_ascii=False, indent=2))"

Write-Host "Starting backend at http://127.0.0.1:8000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
