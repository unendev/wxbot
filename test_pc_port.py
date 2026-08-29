# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)

# Configure Zimaboard .env to use 192.168.50.193:7860
sftp = client.open_sftp()
zima_env = """# 大语言模型配置
LLM_API_URL=http://192.168.50.193:7860/v1/chat/completions
LLM_API_KEY=123456
LLM_MODEL=gemini-3.5-flash-lite
LLM_TEMPERATURE=0.7
"""
with sftp.file("Desktop/wxbot/.env", "w") as f:
    f.write(zima_env)
print("[+] Zimaboard 的 .env 已配置为指向您的 PC (192.168.50.193:7860)！")
sftp.close()

# Test connectivity from Zimaboard to PC port 7860
stdin, stdout, stderr = client.exec_command('powershell -Command "Test-NetConnection -ComputerName 192.168.50.193 -Port 7860"')
out = stdout.read().decode('gbk', errors='ignore')
print("TCP 7860 Test from Zimaboard to PC:\n", out)

client.close()
