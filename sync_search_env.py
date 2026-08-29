# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)

zima_env = """# 大语言模型配置 (实时联网搜索版)
LLM_API_URL=http://192.168.50.193:7860/v1/chat/completions
LLM_API_KEY=123456
LLM_MODEL=gemini-3.5-flash-lite-search
LLM_TEMPERATURE=0.7
"""

sftp = client.open_sftp()
with sftp.file("Desktop/wxbot/.env", "w") as f:
    f.write(zima_env)
print("[+] Zimaboard 上的 .env 已成功更新为 gemini-3.5-flash-lite-search (联网搜索模型)！")
sftp.close()
client.close()
