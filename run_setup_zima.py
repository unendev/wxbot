# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111')

sftp = client.open_sftp()
setup_bat = """@echo off
cd /d "C:\\Users\\zima\\Desktop\\wxbot"
echo [*] Installing dependencies via Tsinghua PyPI mirror...
uv.exe pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
echo [*] Testing imports...
uv.exe run python -c "import uiautomation, requests, PIL, win32gui, dotenv; print('>>> ZIMABOARD ENVIRONMENT 100% READY! <<<')"
"""
with sftp.file("Desktop/wxbot/setup.bat", "w") as f:
    f.write(setup_bat)
sftp.close()

stdin, stdout, stderr = client.exec_command('cmd.exe /c "C:\\Users\\zima\\Desktop\\wxbot\\setup.bat"')
out = stdout.read().decode('gbk', errors='ignore')
err = stderr.read().decode('gbk', errors='ignore')
print("SETUP OUTPUT:\n", out)
if err.strip():
    print("SETUP ERRORS:\n", err)

client.close()
