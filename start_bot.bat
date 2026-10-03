@echo off
chcp 65001 > nul
cd /d %~dp0
echo [*] 正在极速启动微信 AI 机器人...
uv run bot.py
pause

