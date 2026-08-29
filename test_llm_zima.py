# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)

sftp = client.open_sftp()
test_py = """# -*- coding: utf-8 -*-
import sys
from llm_service import call_llm

print("Testing Gemini LLM from Zimaboard...")
res = call_llm("ZimaboardProbe", "你是一台运行在Zimaboard上的AI机器人吗？请用一句话回答。")
print("ACTUAL_LLM_RESPONSE:", res)
"""
with sftp.file("Desktop/wxbot/test_llm.py", "w") as f:
    f.write(test_py.encode('utf-8'))
sftp.close()

stdin, stdout, stderr = client.exec_command('cmd.exe /c "cd /d C:\\Users\\zima\\Desktop\\wxbot & uv.exe run python test_llm.py"')
out = stdout.read().decode('gbk', errors='ignore')
err = stderr.read().decode('gbk', errors='ignore')

print("OUT:\n", out)
if err: print("ERR:\n", err)

client.close()
