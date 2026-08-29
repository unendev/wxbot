# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)

sftp = client.open_sftp()
sftp.put("D:/Study/Vue-/wxbot/bot.py", "Desktop/wxbot/bot.py")

bat_content = """@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "C:\\Users\\zima\\Desktop\\wxbot"
title WeChat AI Bot (Zimaboard)
echo ============================================================
echo   WeChat AI Bot (Zimaboard)
echo ============================================================
echo [*] Starting bot...
uv.exe run bot.py
pause
"""
with sftp.file("Desktop/wxbot/start_bot.bat", "w") as f:
    f.write(bat_content)
with sftp.file("Desktop/启动微信AI机器人.bat", "w") as f:
    f.write(bat_content)

sftp.close()
client.close()
print("[+] 已成功回溯至原始经典版本并同步至 Zimaboard！")
