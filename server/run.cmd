@echo off
cd /d "%~dp0"
set SCORES_ROOT=%~dp0data\scores
REM 管理后台登录账号（与乐谱管理 /admin 一致）
set ADMIN_USERNAME=admin
set ADMIN_PASSWORD=admin
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
