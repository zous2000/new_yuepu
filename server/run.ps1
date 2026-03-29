# 与 run.cmd 相同：固定管理后台为 admin / admin
Set-Location $PSScriptRoot
$env:SCORES_ROOT = Join-Path $PSScriptRoot "data\scores"
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_PASSWORD = "admin"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
