# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=5)

stdin, stdout, stderr = client.exec_command('cmd.exe /c "cd /d C:\\Users\\zima\\Desktop\\wxbot && type steam_mod_cache.json"')
print('CACHE FILE:\n', stdout.read().decode('utf-8', errors='ignore').strip())

stdin, stdout, stderr = client.exec_command('cmd.exe /c "netstat -ano | findstr 5005"')
print('PORT 5005 LISTENER:\n', stdout.read().decode('utf-8', errors='ignore').strip())

stdin, stdout, stderr = client.exec_command('cmd.exe /c "tasklist | findstr python"')
print('RUNNING PYTHON PROCESSES:\n', stdout.read().decode('utf-8', errors='ignore').strip())

client.close()
