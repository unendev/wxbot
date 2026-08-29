# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)

test_py = """# -*- coding: utf-8 -*-
import sys
from llm_service import call_llm

print("Testing Google Web Search from Zimaboard...")
res = call_llm("Probe", "请简要查询：今天人民币对美元汇率是多少？一句话回答即可。")
print("SEARCH_RESULT:", res)
"""
sftp = client.open_sftp()
with sftp.file("Desktop/wxbot/test_search.py", "w") as f:
    f.write(test_py.encode('utf-8'))
sftp.close()

stdin, stdout, stderr = client.exec_command('cmd.exe /c "chcp 65001 >nul & set PYTHONIOENCODING=utf-8 & cd /d C:\\Users\\zima\\Desktop\\wxbot & uv.exe run python test_search.py"')
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')

print("OUT:\n", out.strip())
if err: print("ERR:\n", err.strip())

client.close()
