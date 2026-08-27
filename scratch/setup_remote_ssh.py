# -*- coding: utf-8 -*-
import sys
import os
import time
import paramiko

ZIMA_IP = "192.168.50.109"
ZIMA_USER = "Zima"
ZIMA_PASS = "12345678"

# 我们在主力机上获取的公钥
PUB_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAJ/jSvZ2ii6TPMFpv7ykb7TrJ5OfkCWol85zek1h3pQ a1634@pianoWithin"

def main():
    print(f"[*] 正在尝试使用密码密码登录 Zima IP: {ZIMA_IP}...")
    
    # 1. 初始化 SSH 客户端
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(ZIMA_IP, username=ZIMA_USER, password=ZIMA_PASS, timeout=10)
        print("[+] 成功登录 Zimaboard 远程系统！")
    except Exception as e:
        print(f"[X] 错误：无法通过 SSH 连接到 Zimaboard: {e}")
        return
        
    # 2. 通过 SFTP 写入公钥文件 (彻底规避命令行引号转义地狱)
    print("[*] 正在通过 SFTP 写入公钥数据...")
    try:
        sftp = ssh.open_sftp()
        
        # 写入用户 ~/.ssh/authorized_keys
        try:
            sftp.mkdir("C:/Users/Zima/.ssh")
        except Exception:
            pass
        with sftp.file("C:/Users/Zima/.ssh/authorized_keys", "w") as f:
            f.write(PUB_KEY + "\n")
        print("[+] 成功写入 C:/Users/Zima/.ssh/authorized_keys")
        
        # 写入公用 administrators_authorized_keys
        try:
            sftp.mkdir("C:/ProgramData/ssh")
        except Exception:
            pass
        admin_file_path = "C:/ProgramData/ssh/administrators_authorized_keys"
        with sftp.file(admin_file_path, "w") as f:
            f.write(PUB_KEY + "\n")
        print("[+] 成功写入 C:/ProgramData/ssh/administrators_authorized_keys")
        
        sftp.close()
    except Exception as exc:
        print(f"[X] 错误：SFTP 传输失败: {exc}")
        ssh.close()
        return
        
    # 3. 锁定管理员公钥文件的安全权限 (Windows 极其严格的要求)
    print("[*] 正在锁定管理员公钥文件的安全访问权限 (icacls)...")
    acl_cmd = 'icacls C:\\ProgramData\\ssh\\administrators_authorized_keys /inheritance:r /grant SYSTEM:(F) /grant Administrators:(F)'
    stdin, stdout, stderr = ssh.exec_command(acl_cmd)
    out_err = stderr.read().decode('utf-8', errors='ignore')
    if out_err:
        print(f"[-] icacls 权限设定警告: {out_err}")
    else:
        print("[+] 成功赋予 SYSTEM 和 Administrators 独占读写权限！")
        
    # 4. 远程重启 SSH 服务以加载配置
    print("[*] 正在重启远程 SSH 服务...")
    restart_cmd = 'powershell -Command "Restart-Service sshd"'
    stdin, stdout, stderr = ssh.exec_command(restart_cmd)
    time.sleep(1.5)
    
    ssh.close()
    print("[*] 密码通道断开，正在进行第二次免密握手测试...")
    time.sleep(1)
    
    # 5. 测试免密密钥对登录
    ssh_key = paramiko.SSHClient()
    ssh_key.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    private_key_path = os.path.expanduser("~/.ssh/id_ed25519")
    
    try:
        key = paramiko.Ed25519Key.from_private_key_file(private_key_path)
        print(f"[*] 正在尝试免密码登录...")
        ssh_key.connect(ZIMA_IP, username=ZIMA_USER, pkey=key, timeout=10)
        
        stdin, stdout, stderr = ssh_key.exec_command("whoami")
        result = stdout.read().decode('utf-8').strip()
        print(f"[√] 免密握手大获全胜！！！")
        print(f"    - 登录用户名: '{result}'")
    except Exception as err:
        print(f"[X] 免密验证失败: {err}")
    finally:
        ssh_key.close()

if __name__ == "__main__":
    main()
