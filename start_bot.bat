@echo off
cd /d %~dp0
echo [*] 使用 uv 极速环境启动微信智能机器人...
uv run python main.py
if %ERRORLEVEL% NEQ 0 (
    echo [!] 尝试降级使用虚拟环境启动...
    call .venv\Scripts\activate.bat
    python main.py
)
pause
