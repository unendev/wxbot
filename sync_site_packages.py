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

def ensure_remote_dir(remote_dir):
    parts = remote_dir.replace('\\', '/').strip('/').split('/')
    cur = ""
    for p in parts:
        cur += p + "/"
        try:
            sftp.mkdir(cur)
        except Exception:
            pass

local_site_packages = Path("D:/Study/Vue-/wxbot/.venv/Lib/site-packages")
remote_site_packages = "Desktop/wxbot/.venv/Lib/site-packages"

ensure_remote_dir(remote_site_packages)

print(f"[*] 正在将本地已构建完成的 Python 依赖库直传至 Zimaboard (零外网依赖)...")

count = 0
for root, dirs, files in os.walk(local_site_packages):
    rel_path = Path(root).relative_to(local_site_packages)
    r_dir = f"{remote_site_packages}/{str(rel_path).replace(chr(92), '/')}".rstrip('/')
    ensure_remote_dir(r_dir)
    for f in files:
        if f.endswith('.pyc') or '__pycache__' in root:
            continue
        local_fp = Path(root) / f
        remote_fp = f"{r_dir}/{f}"
        sftp.put(str(local_fp), remote_fp)
        count += 1
        if count % 100 == 0:
            print(f"[*] 已直传 {count} 个核心依赖文件...")

print(f"[+] 依赖库直传完毕，共同步 {count} 个文件！")

sftp.close()

# 验证导入
print("[*] 正在验证 Zimaboard 依赖环境...")
stdin, stdout, stderr = client.exec_command('powershell -Command "cd C:\\Users\\zima\\Desktop\\wxbot; .\\uv.exe run python -c \\\"import uiautomation, requests, PIL, win32gui, dotenv; print(\'ALL DEPENDENCIES 100% READY ON ZIMABOARD!\')\\\""')
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')

print("OUT:", out.strip())
if err.strip():
    print("ERR:", err.strip())

client.close()
print("\n[√] Zimaboard 全量部署圆满完成！")
