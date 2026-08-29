# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111')

def run(cmd):
    print(f"=== CMD: {cmd} ===")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('gbk', errors='ignore').strip()
    err = stderr.read().decode('gbk', errors='ignore').strip()
    if out: print(out)
    if err: print("ERR:", err)
    return out

run("qwinsta")
run("query user")
run("sc query TermService")
run('reg query "HKLM\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp"')

client.close()
