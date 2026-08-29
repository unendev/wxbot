@echo off
chcp 65001 >nul
title Steam MOD Monitor (Zimaboard)
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0"

echo ===================================================
echo   Steam Workshop Mod Monitor (5m Poller)
echo ===================================================
echo [*] Starting monitor...

if exist uv.exe (
    uv.exe run python steam_mod_monitor.py
) else (
    .venv\Scripts\python.exe steam_mod_monitor.py
)

pause
