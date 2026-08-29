# -*- coding: utf-8 -*-
import paramiko
from pathlib import Path

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)

sftp = client.open_sftp()
sftp.put("D:/Study/Vue-/wxbot/llm_service.py", "Desktop/wxbot/llm_service.py")
sftp.put("D:/Study/Vue-/wxbot/.env", "Desktop/wxbot/.env")
sftp.close()

# Run the test call
stdin, stdout, stderr = client.exec_command('cmd.exe /c "cd /d C:\\Users\\zima\\Desktop\\wxbot & uv.exe run python -c \"import uiautomation, requests, PIL, win32gui, dotenv; from llm_service import call_llm; print(\'LLM_RESPONSE:\', call_llm(\'ZimaboardSelfCheck\', \'hello\'))\""')

out = stdout.read().decode('gbk', errors='ignore')
err = stderr.read().decode('gbk', errors='ignore')

print("OUT:\n", out)
if err: print("ERR:\n", err)

client.close()
