# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)
sftp = client.open_sftp()

steam_bat = """@echo off
chcp 65001 >nul
title Steam MOD Monitor (Zimaboard)
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "C:\\Users\\zima\\Desktop\\wxbot"

echo ===================================================
echo   Steam Workshop Mod Monitor (5m Poller)
echo ===================================================
echo [*] Starting monitor...

if exist uv.exe (
    uv.exe run python steam_mod_monitor.py
) else (
    .venv\\Scripts\\python.exe steam_mod_monitor.py
)

pause
"""

with sftp.file("Desktop/启动Steam数据监控.bat", "w") as f:
    f.write(steam_bat.encode('utf-8'))

desktop_items = sftp.listdir("Desktop")
print("Desktop items now:", desktop_items)

sftp.close()
client.close()
print("[+] Successfully generated 启动Steam数据监控.bat on Desktop!")
