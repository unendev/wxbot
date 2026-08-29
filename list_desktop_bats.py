# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=5)
sftp = client.open_sftp()
print("CURRENT BATS ON DESKTOP:")
for f in sftp.listdir('Desktop'):
    if f.endswith('.bat'):
        print(" -", repr(f))
sftp.close()
client.close()
