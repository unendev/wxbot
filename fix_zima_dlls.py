# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)

sftp = client.open_sftp()
fix_bat = """@echo off
cd /d "C:\\Users\\zima\\Desktop\\wxbot"
copy /y .venv\\Lib\\site-packages\\pywin32_system32\\* .venv\\Lib\\site-packages\\win32\\
copy /y .venv\\Lib\\site-packages\\pywin32_system32\\* .venv\\Lib\\site-packages\\
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
uv.exe run python probe_ui.py
"""
with sftp.file("Desktop/wxbot/fix_dll.bat", "w") as f:
    f.write(fix_bat)
sftp.close()

stdin, stdout, stderr = client.exec_command('cmd.exe /c "C:\\Users\\zima\\Desktop\\wxbot\\fix_dll.bat"')
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')

print("OUT:\n", out.strip())
if err: print("ERR:\n", err.strip())

client.close()
