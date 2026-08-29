# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=5)

stdin, stdout, stderr = client.exec_command('cmd.exe /c "cd /d C:\\Users\\zima\\Desktop\\wxbot && uv.exe run python -c \"import steam_mod_monitor; print(\'TARGET:\', repr(steam_mod_monitor.PUSH_TARGET))\""')
print("OUTPUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("ERR:\n", stderr.read().decode('utf-8', errors='ignore'))
client.close()
