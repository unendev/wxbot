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
print("[+] SSH 连接成功！")

sftp = client.open_sftp()

# 1. 确保 Desktop/wxbot 目录存在
try:
    sftp.mkdir("Desktop/wxbot")
except Exception:
    pass

# 2. 上传 uv.exe
local_uv = Path("C:/Users/a1634/AppData/Local/Programs/Python/Python311/Scripts/uv.exe")
if local_uv.exists():
    print(f"[*] 正在上传 uv.exe ({local_uv.stat().st_size // 1024 // 1024} MB)...")
    sftp.put(str(local_uv), "Desktop/wxbot/uv.exe")
    print("[+] uv.exe 上传成功！")

# 3. 上传核心代码与配置文件
files_to_upload = [
    "bot.py",
    "llm_service.py",
    "requirements.txt",
    ".env",
]

for fname in files_to_upload:
    local_f = Path(f"D:/Study/Vue-/wxbot/{fname}")
    if local_f.exists():
        print(f"[*] 正在上传 {fname}...")
        sftp.put(str(local_f), f"Desktop/wxbot/{fname}")
        print(f"[+] {fname} 同步完毕")

# 4. 生成启动脚本
bat_content = """@echo off
chcp 65001 >nul
cd /d "%USERPROFILE%\\Desktop\\wxbot"
title 微信 AI 智能助手 (Zimaboard)
echo ============================================================
echo   微信 AI 智能助手 (Zimaboard 专属服务)
echo ============================================================
echo [*] 正在启动机器人服务，请确保微信已登录并拖出目标窗口...
uv.exe run bot.py
pause
"""

with sftp.file("Desktop/wxbot/start_bot.bat", "w") as f:
    f.write(bat_content)

with sftp.file("Desktop/启动微信AI机器人.bat", "w") as f:
    f.write(bat_content)

print("[+] 桌面一键启动脚本已生成至: Desktop/启动微信AI机器人.bat")
sftp.close()

# 5. 在 Zimaboard 上预热安装 Python 依赖
print("[*] 正在 Zimaboard 上预热构建虚拟环境与安装依赖 (uv pip install)...")
stdin, stdout, stderr = client.exec_command('cd Desktop/wxbot; .\\uv.exe venv; .\\uv.exe pip install -r requirements.txt; .\\uv.exe run python -c "print(\'=== Zimaboard Python 环境预热成功！===\')"')
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')

if out.strip():
    print(out.strip())
if err.strip():
    print("Notice:", err.strip())

client.close()
print("\n[√] 恭喜！Zimaboard 全量自动部署圆满完成！")
