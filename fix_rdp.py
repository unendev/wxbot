# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111')

def run(cmd):
    print(f"[*] CMD: {cmd}")
    stdin, stdout, stderr = client.exec_command(f'powershell -Command "{cmd}"')
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    if out: print("OUT:", out)
    if err: print("ERR:", err)
    return out

# 1. 开启远程桌面 fDenyTSConnections = 0
run("Set-ItemProperty -Path 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server' -Name 'fDenyTSConnections' -Value 0")

# 2. 关闭 NLA (网络级别身份验证)，允许所有标准 RDP 客户端直接连接输入密码
run("Set-ItemProperty -Path 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp' -Name 'UserAuthentication' -Value 0")

# 3. 确保防火墙放行 3389
run("Enable-NetFirewallRule -DisplayGroup 'Remote Desktop' -ErrorAction SilentlyContinue")
run("Enable-NetFirewallRule -Name 'RemoteDesktop-UserMode-In-TCP' -ErrorAction SilentlyContinue")

# 4. 确保 zima 用户在 Remote Desktop Users 组中
run("Add-LocalGroupMember -Group 'Remote Desktop Users' -Member 'zima' -ErrorAction SilentlyContinue")

# 5. 重启 TermService 远程桌面服务使其立即生效
run("Restart-Service -Name TermService -Force")

print("\n[+] RDP 服务已全面修复并重置（已禁用 NLA 鉴权阻碍，已放行防火墙）！")
client.close()
