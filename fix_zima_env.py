# -*- coding: utf-8 -*-
import paramiko
from pathlib import Path

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)

sftp = client.open_sftp()

# 1. 确保将真实的 local .env 完整写入远端
local_env = Path("D:/Study/Vue-/wxbot/.env")
if local_env.exists():
    content = local_env.read_text(encoding='utf-8')
    print("[*] Local .env content size:", len(content))
    with sftp.file("Desktop/wxbot/.env", "w") as f:
        f.write(content)
    print("[+] .env 成功写入 Zimaboard！")

# 2. 清理并用纯净的 Python 3.10 wheels 进行规范安装
cmd_install = """@echo off
cd /d "C:\\Users\\zima\\Desktop\\wxbot"
echo [*] Installing exact Python 3.10 wheels...
uv.exe pip install --no-index --find-links wheels uiautomation pywin32 requests pillow python-dotenv
echo [*] Running pywin32 postinstall...
uv.exe run python -c "import uiautomation, requests, PIL, win32gui, dotenv; print('ALL_LIBS_SUCCESSFULLY_LOADED')"
"""
with sftp.file("Desktop/wxbot/install.bat", "w") as f:
    f.write(cmd_install)
sftp.close()

# 3. 执行安装
stdin, stdout, stderr = client.exec_command('cmd.exe /c "C:\\Users\\zima\\Desktop\\wxbot\\install.bat"')
out = stdout.read().decode('gbk', errors='ignore')
err = stderr.read().decode('gbk', errors='ignore')

print("INSTALL OUTPUT:\n", out)
if err: print("INSTALL ERROR:\n", err)

client.close()
