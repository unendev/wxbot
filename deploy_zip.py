# -*- coding: utf-8 -*-
import os
import shutil
import zipfile
import paramiko
from pathlib import Path

host = '192.168.50.109'
user = 'zima'
password = '131232111'

local_site_packages = Path("D:/Study/Vue-/wxbot/.venv/Lib/site-packages")
zip_path = Path("D:/Study/Vue-/wxbot/site_packages.zip")

print("[*] 正在本地打包 Python 核心依赖库 (ZIP 压缩)...")
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(local_site_packages):
        for f in files:
            if '__pycache__' in root or f.endswith('.pyc'):
                continue
            fp = Path(root) / f
            arcname = fp.relative_to(local_site_packages)
            zipf.write(fp, arcname)

print(f"[+] 打包完成！ZIP 文件大小: {zip_path.stat().st_size // 1024 // 1024} MB")

print(f"[*] 正在连接 Zimaboard ({host})...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, port=22, username=user, password=password, timeout=10)

sftp = client.open_sftp()
print("[*] 正在极速上传 site_packages.zip 到 Zimaboard...")
sftp.put(str(zip_path), "Desktop/wxbot/site_packages.zip")
print("[+] ZIP 压缩包上传完毕！")
sftp.close()

print("[*] 正在 Zimaboard 上解压并就绪运行环境...")
cmd = (
    'powershell -Command "'
    'Expand-Archive -Force -Path C:\\Users\\zima\\Desktop\\wxbot\\site_packages.zip -DestinationPath C:\\Users\\zima\\Desktop\\wxbot\\.venv\\Lib\\site-packages; '
    'Remove-Item C:\\Users\\zima\\Desktop\\wxbot\\site_packages.zip; '
    'cd C:\\Users\\zima\\Desktop\\wxbot; '
    '.\\uv.exe run python -c \\\"import uiautomation, requests, PIL, win32gui, dotenv; print(\'>>> ZIMABOARD 微信 AI 助手运行环境 100% 验证就绪！<<<\')\\\"'
    '"'
)
stdin, stdout, stderr = client.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')

print("OUT:\n", out.strip())
if err.strip():
    print("ERR:\n", err.strip())

client.close()
zip_path.unlink(missing_ok=True)
print("\n[√] 部署大功告成！")
