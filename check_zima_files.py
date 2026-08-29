# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111')

sftp = client.open_sftp()
print("Desktop contents:", sftp.listdir("Desktop"))
print("Desktop/wxbot contents:", sftp.listdir("Desktop/wxbot"))
sftp.close()
client.close()
