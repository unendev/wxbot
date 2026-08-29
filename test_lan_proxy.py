# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)

sftp = client.open_sftp()
test_env = """# 大语言模型配置
LLM_API_URL=http://192.168.50.193:7860/v1/chat/completions
LLM_API_KEY=123456
LLM_MODEL=gemini-3.5-flash-lite
LLM_TEMPERATURE=0.7
"""
with sftp.file("Desktop/wxbot/.env", "w") as f:
    f.write(test_env)

test_py = """# -*- coding: utf-8 -*-
import sys
from llm_service import call_llm

res = call_llm("Probe", "你好，请用一句话回答。")
print("LLM_RESPONSE:", res)
"""
with sftp.file("Desktop/wxbot/test_llm.py", "w") as f:
    f.write(test_py.encode('utf-8'))
sftp.close()

stdin, stdout, stderr = client.exec_command('cmd.exe /c "chcp 65001 >nul & cd /d C:\\Users\\zima\\Desktop\\wxbot & uv.exe run python test_llm.py"')
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')

print("OUT:\n", out.strip())
if err.strip():
    print("ERR:\n", err.strip())

client.close()
