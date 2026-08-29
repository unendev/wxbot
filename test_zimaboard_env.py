# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111')

sftp = client.open_sftp()
test_bat = """@echo off
cd /d "C:\\Users\\zima\\Desktop\\wxbot"
uv.exe pip install --find-links wheels/ -r requirements.txt
uv.exe run python -c "import uiautomation, requests, PIL, win32gui, dotenv; print('ENVIRONMENT 100 PERCENT VERIFIED!')"
"""
with sftp.file("Desktop/wxbot/test_run.bat", "w") as f:
    f.write(test_bat)
sftp.close()

stdin, stdout, stderr = client.exec_command('cmd.exe /c "C:\\Users\\zima\\Desktop\\wxbot\\test_run.bat"')
out = stdout.read().decode('gbk', errors='ignore')
err = stderr.read().decode('gbk', errors='ignore')
print("OUTPUT:\n", out)
if err.strip():
    print("ERRORS:\n", err)

client.close()
