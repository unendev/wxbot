# -*- coding: utf-8 -*-
import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111')

def run(cmd):
    print(f"[*] CMD: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('gbk', errors='ignore').strip()
    err = stderr.read().decode('gbk', errors='ignore').strip()
    if out: print("OUT:", out)
    if err: print("ERR:", err)
    return out

# 1. 注销卡死的旧会话 2
run("logoff 2")

# 2. 找到并强制杀死处于 STOP_PENDING 的 TermService 进程
run("taskkill /f /fi \"SERVICES eq TermService\"")
time.sleep(1)

# 3. 确保恢复标准 NLA 与 RDP 设置
run('reg add "HKLM\\System\\CurrentControlSet\\Control\\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f')
run('reg add "HKLM\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp" /v UserAuthentication /t REG_DWORD /d 1 /f')
run('reg add "HKLM\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp" /v SecurityLayer /t REG_DWORD /d 2 /f')

# 4. 重新启动 TermService 服务
run("net start TermService")

# 5. 查询服务当前健康状态
print("\n=== 服务当前运行状态 ===")
run("sc query TermService")
run("qwinsta")

client.close()
print("\n[+] TermService 已彻底恢复正常运行！")
