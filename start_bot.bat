@echo off
chcp 65001 >nul
title 微信静默智能机器人 (副屏/多屏兼容)

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo ========================================================
echo   微信静默智能机器人已启动
echo   请确保微信小号窗口在屏幕上（主屏/副屏均可，勿最小化到托盘）
echo ========================================================
echo.
"%PYTHON_EXE%" main.py
pause
