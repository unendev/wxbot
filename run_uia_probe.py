# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=5)
sftp = client.open_sftp()
sftp.put('D:/Study/Vue-/wxbot/probe_uia_top.py', 'Desktop/wxbot/probe_uia_top.py')
sftp.close()

stdin, stdout, stderr = client.exec_command('cmd.exe /c "cd /d C:\\Users\\zima\\Desktop\\wxbot && uv.exe run python probe_uia_top.py"')
print(stdout.read().decode('utf-8', errors='ignore'))
client.close()
