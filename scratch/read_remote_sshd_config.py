# -*- coding: utf-8 -*-
import paramiko

ZIMA_IP = "192.168.50.109"
ZIMA_USER = "Zima"
ZIMA_PASS = "12345678"

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ZIMA_IP, username=ZIMA_USER, password=ZIMA_PASS, timeout=10)
    
    # 读取 sshd_config 后 15 行
    cmd = 'powershell -Command "Get-Content C:\\ProgramData\\ssh\\sshd_config | Select-Object -Last 15"'
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    print("=== Zima sshd_config Last 15 Lines ===")
    print(stdout.read().decode('utf-8', errors='ignore'))
    print("======================================")
    
    # 顺便读取一下 authorized_keys 看看里面的内容对不对
    cmd2 = 'powershell -Command "Get-Content C:\\Users\\Zima\\.ssh\\authorized_keys"'
    stdin2, stdout2, stderr2 = ssh.exec_command(cmd2)
    print("\n=== Zima authorized_keys ===")
    print(stdout2.read().decode('utf-8', errors='ignore'))
    print("==============================")
    
    ssh.close()

if __name__ == "__main__":
    main()
