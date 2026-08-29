# -*- coding: utf-8 -*-
import paramiko
import json

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('gbk', errors='ignore').strip()
    err = stderr.read().decode('gbk', errors='ignore').strip()
    return out, err

print("=== 1. 检查桌面核心文件与配置 ===")
out, _ = run('cmd.exe /c "cd /d %USERPROFILE%\\Desktop\\wxbot & dir /b bot.py llm_service.py .env uv.exe & dir /b %USERPROFILE%\\Desktop\\*机器人*.bat"')
print(out)

print("\n=== 2. 检查所有 Python 底层依赖导入 (零缺失验证) ===")
out, err = run('cmd.exe /c "cd /d %USERPROFILE%\\Desktop\\wxbot & uv.exe run python -c \"import uiautomation, requests, PIL, win32gui, dotenv; print(\'ALL_LIBS_LOADED_100_PERCENT\')\""')
print("OUT:", out)
if err: print("ERR:", err)

print("\n=== 3. 检查 Zimaboard 到 Gemini 大模型 API 的网络连通性 ===")
out, err = run('cmd.exe /c "cd /d %USERPROFILE%\\Desktop\\wxbot & uv.exe run python -c \"from llm_service import call_llm; res = call_llm(\'SelfTest\', \'ping\'); print(\'LLM_TEST_RESPONSE:\', res)\""')
print("OUT:", out)
if err: print("ERR:", err)

print("\n=== 4. 检查微信进程是否已在后台就绪 ===")
out, _ = run('cmd.exe /c "tasklist | findstr /i WeChat.exe"')
print(out if out else "微信尚未运行（请在桌面打开登录微信并拖出窗口）")

client.close()
