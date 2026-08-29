# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111')

sftp = client.open_sftp()
print("SFTP current directory:", sftp.getcwd())
try:
    print("SFTP listdir:", sftp.listdir())
except Exception as e:
    print("SFTP listdir err:", e)

# Test creating wxbot in user home directory
try:
    sftp.mkdir("Desktop")
except Exception:
    pass

try:
    sftp.mkdir("Desktop/wxbot")
except Exception:
    pass

print("SFTP Desktop/wxbot exists!")
sftp.close()
client.close()
