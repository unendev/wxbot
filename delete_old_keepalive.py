# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=5)
sftp = client.open_sftp()
for f in sftp.listdir('Desktop'):
    if f.endswith('.bat') and ('后台保活' in f or '切控制台' in f):
        try:
            sftp.remove('Desktop/' + f)
            print('Successfully deleted old file:', f)
        except Exception as e:
            print('Error deleting:', f, e)
sftp.close()
client.close()
