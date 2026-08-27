@echo off
chcp 65001 >nul
title 微信静默智能机器人

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [*] 正在启动微信机器人...
"%PYTHON_EXE%" main.py
pause
