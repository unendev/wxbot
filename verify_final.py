# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111')

sftp = client.open_sftp()
print("SFTP Desktop/wxbot files:", sftp.listdir("Desktop/wxbot"))
sftp.close()

# Use %USERPROFILE% in cmd.exe
cmd = 'cmd.exe /c "cd /d %USERPROFILE%\\Desktop\\wxbot & powershell -Command \"Expand-Archive -Force -Path .\\site_packages.zip -DestinationPath .\\.venv\\Lib\\site-packages; Remove-Item .\\site_packages.zip -ErrorAction SilentlyContinue\" & uv.exe run python -c \"import uiautomation, requests, PIL, win32gui, dotenv; print(\'ALL MODULES VERIFIED 100 PERCENT OK!\')\""'

stdin, stdout, stderr = client.exec_command(cmd)
out = stdout.read().decode('gbk', errors='ignore')
err = stderr.read().decode('gbk', errors='ignore')

print("OUT:\n", out.strip())
if err.strip():
    print("ERR:\n", err.strip())

client.close()
