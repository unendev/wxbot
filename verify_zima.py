# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111')

# Clean up bat name to standard ANSI/GBK
sftp = client.open_sftp()
bat_content = """@echo off
chcp 65001 >nul
cd /d "C:\\Users\\zima\\Desktop\\wxbot"
title WeChat AI Bot (Zimaboard)
echo ============================================================
echo   WeChat AI Bot (Zimaboard)
echo ============================================================
echo [*] Starting bot...
uv.exe run bot.py
pause
"""
with sftp.file("Desktop/启动微信AI机器人.bat", "w") as f:
    f.write(bat_content)
with sftp.file("Desktop/wxbot/start_bot.bat", "w") as f:
    f.write(bat_content)
sftp.close()

# Run uv pre-warm
stdin, stdout, stderr = client.exec_command('cmd.exe /c "cd /d C:\\Users\\zima\\Desktop\\wxbot & uv.exe run python -c \"import uiautomation, requests, PIL, win32gui; print(\'ALL DEPENDENCIES OK\')\""')
out = stdout.read().decode('gbk', errors='ignore')
err = stderr.read().decode('gbk', errors='ignore')
print("STDOUT:", out.strip())
print("STDERR:", err.strip())

client.close()
