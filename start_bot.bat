@echo off
title WeChat RPA Bot 24H Keeper

cd /d "%~dp0"
echo ======================================================
echo        WeChat RPA Bot 24H Keeper is running
echo ======================================================
echo [*] Current Directory: %cd%

:loop
echo [*] Launching bot.py...
call .venv\Scripts\python.exe -u bot.py

echo [!] Warning: Bot process exited! Restarting in 5s...
timeout /t 5 >nul
goto loop
