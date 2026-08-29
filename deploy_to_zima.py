# -*- coding: utf-8 -*-
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

def run_cmd(cmd):
    print(f"[*] 执行命令: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore')
    err = stderr.read().decode('utf-8', errors='ignore')
    if out.strip():
        print(out.strip())
    if err.strip():
        print("Log/Notice:", err.strip())
    return out, err

# 1. 检查并安装 uv
run_cmd("powershell -ExecutionPolicy ByPass -Command \"if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { irm https://astral.sh/uv/install.ps1 | iex }\"")

# 2. 检查桌面并拉取最新仓库
run_cmd("powershell -Command \"if (Test-Path C:\\Users\\zima\\Desktop\\wxbot) { cd C:\\Users\\zima\\Desktop\\wxbot; git pull } else { git clone https://github.com/unendev/wxbot.git C:\\Users\\zima\\Desktop\\wxbot }\"")

# 3. 通过 SFTP 上传包含 API Key 的 .env 文件
sftp = client.open_sftp()
local_env = Path("D:/Study/Vue-/wxbot/.env")
remote_env = "C:/Users/zima/Desktop/wxbot/.env"
if local_env.exists():
    print(f"[*] 正在同步配置文件 .env -> {remote_env}...")
    sftp.put(str(local_env), remote_env)
    print("[+] .env 配置文件传输完毕！")

# 4. 创建桌面的 启动微信机器人.bat
bat_content = """@echo off
chcp 65001 >nul
cd /d "C:\\Users\\zima\\Desktop\\wxbot"
title 微信 AI 智能助手
echo ============================================================
echo   微信 AI 智能助手 (Zimaboard 专属服务)
echo ============================================================
echo [*] 正在启动机器人服务，请确保微信已登录并拖出目标窗口...
set PATH=%USERPROFILE%\\.local\\bin;%PATH%
uv run bot.py
pause
"""

remote_bat = "C:/Users/zima/Desktop/wxbot/start_bot.bat"
desktop_bat = "C:/Users/zima/Desktop/启动微信机器人.bat"

with sftp.file(remote_bat, "w") as f:
    f.write(bat_content)
with sftp.file(desktop_bat, "w") as f:
    f.write(bat_content)
print("[+] 桌面一键启动脚本生成成功: C:\\Users\\zima\\Desktop\\启动微信机器人.bat")

sftp.close()

# 5. 在 Zimaboard 上执行 uv 同步与预热
run_cmd("powershell -Command \"$env:Path += ';C:\\Users\\zima\\.local\\bin'; cd C:\\Users\\zima\\Desktop\\wxbot; uv run python -c \\\"print('Zimaboard Python 环境就绪')\\\"\"")

client.close()
print("\n[√] Zimaboard 全量部署圆满完成！")
