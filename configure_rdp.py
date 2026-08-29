# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111')

# 1. 强制重置密码为 131232111
stdin, stdout, stderr = client.exec_command('net user zima 131232111')
print("Reset password:", stdout.read().decode('gbk', errors='ignore').strip())

# 2. 开启远程桌面
stdin, stdout, stderr = client.exec_command('reg add "HKLM\\System\\CurrentControlSet\\Control\\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f')
print("Enable RDP:", stdout.read().decode('gbk', errors='ignore').strip())

# 3. 关闭 NLA (解决凭据协商与黑屏问题)
stdin, stdout, stderr = client.exec_command('reg add "HKLM\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp" /v UserAuthentication /t REG_DWORD /d 0 /f')
print("Disable NLA:", stdout.read().decode('gbk', errors='ignore').strip())

# 4. 防火墙放行
stdin, stdout, stderr = client.exec_command('netsh advfirewall firewall set rule group="remote desktop" new enable=Yes')
print("Firewall:", stdout.read().decode('gbk', errors='ignore').strip())

client.close()
print("\n[+] 远程桌面策略与密码已全部强制就绪！")
