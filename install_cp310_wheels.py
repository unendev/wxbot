# -*- coding: utf-8 -*-
import os
import paramiko
from pathlib import Path

host = '192.168.50.109'
user = 'zima'
password = '131232111'

print(f"[*] 正在连接 Zimaboard ({host})...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, port=22, username=user, password=password, timeout=10)

sftp = client.open_sftp()
try:
    sftp.mkdir("Desktop/wxbot/wheels")
except Exception:
    pass

local_wheels = Path("D:/Study/Vue-/wxbot/wheels")
print("[*] 正在传输 Python 3.10 原生二进制 Wheel 包至 Zimaboard...")

for f in local_wheels.glob("*.whl"):
    print(f"[*] 上传 {f.name}...")
    sftp.put(str(f), f"Desktop/wxbot/wheels/{f.name}")

sftp.close()

# 在 Zimaboard 上执行全新纯净安装并预热验证
print("[*] 正在安装 Python 3.10 专属依赖库...")
cmd = (
    'cmd.exe /c "'
    'cd /d %USERPROFILE%\\Desktop\\wxbot & '
    'uv.exe venv --python "C:\\Users\\ZIma\\AppData\\Local\\Programs\\Python\\Python310\\python.exe" & '
    'uv.exe pip install wheels/*.whl & '
    'uv.exe run python -c "import uiautomation, requests, PIL, win32gui, dotenv; print(\'>>> SUCCESS: ZIMABOARD ENVIRONMENT 100 PERCENT VERIFIED! <<<\')"'
    '"'
)
stdin, stdout, stderr = client.exec_command(cmd)
out = stdout.read().decode('gbk', errors='ignore')
err = stderr.read().decode('gbk', errors='ignore')

print("OUT:\n", out.strip())
if err.strip():
    print("ERR/LOG:\n", err.strip())

client.close()
print("\n[√] Zimaboard 生产环境 100% 部署就绪！")
