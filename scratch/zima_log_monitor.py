# -*- coding: utf-8 -*-
import sys
import os
import paramiko

ZIMA_IP = "192.168.50.109"
ZIMA_USER = "Zima"

def main():
    private_key_path = os.path.expanduser("~/.ssh/id_ed25519")
    if not os.path.exists(private_key_path):
        print(f"[X] 错误：未找到 SSH 私钥 {private_key_path}")
        return

    print(f"[*] 正在通过 SSH 密钥连接 Zima ({ZIMA_IP})...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        key = paramiko.Ed25519Key.from_private_key_file(private_key_path)
        ssh.connect(ZIMA_IP, username=ZIMA_USER, pkey=key, timeout=10)
        print("[+] SSH 连接成功！")
    except Exception as e:
        print(f"[X] SSH 连接失败: {e}")
        return

    print("[*] 正在 Zima 上远程拉起微信机器人 bot.py 并以行级流式抓取实时日志...")
    cmd = "C:/wxbot/.venv/Scripts/python.exe -u C:/wxbot/bot.py"
    
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        
        # 使用 readline 实时以 Streaming 方式读出 Zima 上打印的每一行
        while True:
            line = stdout.readline()
            if not line:
                # 检查 stderr 看看是不是报错退出了
                err_line = stderr.readline()
                if err_line:
                    print(f"[远程报错] {err_line.strip()}")
                else:
                    break
            else:
                print(f"[Zima Bot] {line.strip()}")
                
    except KeyboardInterrupt:
        print("\n[*] 停止监听。")
    except Exception as e:
        print(f"[X] 运行出错: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
