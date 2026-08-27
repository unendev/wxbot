# -*- coding: utf-8 -*-
import sys
import os
import time
import paramiko

ZIMA_IP = "192.168.50.109"
ZIMA_USER = "Zima"

def main():
    private_key_path = os.path.expanduser("~/.ssh/id_ed25519")
    if not os.path.exists(private_key_path):
        print(f"[X] 错误：未找到 SSH 私钥: {private_key_path}")
        return

    print(f"[*] 正在连接 Zima SSH ({ZIMA_IP})...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        key = paramiko.Ed25519Key.from_private_key_file(private_key_path)
        ssh.connect(ZIMA_IP, username=ZIMA_USER, pkey=key, timeout=10)
        print("[+] 连接成功！")
    except Exception as e:
        print(f"[X] 无法连接: {e}")
        return

    # 1. 杀死 Zima 上冲突的 Python 进程
    print("[*] 正在远程清理 Zima 上的冲突进程与旧诊断文件...")
    ssh.exec_command('taskkill /f /im python.exe')
    ssh.exec_command('schtasks /delete /tn "ZimaDiag" /f')
    ssh.exec_command('cmd.exe /c "del /q C:\\wxbot\\diagnose.txt"')
    time.sleep(1)

    # 2. 上传 diagnose_group_name.py 到 Zima
    print("[*] 正在上传诊断测试脚本...")
    try:
        sftp = ssh.open_sftp()
        sftp.put("scratch/diagnose_group_name.py", "C:/wxbot/scratch/diagnose_group_name.py")
        sftp.close()
        print("[+] 上传成功！")
    except Exception as e:
        print(f"[X] 上传失败: {e}")
        ssh.close()
        return

    # 3. 注册临时交互式特权任务以穿透 Session 0 限制
    print("[*] 正在远程注册交互式诊断任务 (schtasks)...")
    task_cmd = (
        'schtasks /create /tn "ZimaDiag" '
        '/tr "C:\\wxbot\\.venv\\Scripts\\python.exe C:\\wxbot\\scratch\\diagnose_group_name.py" '
        '/sc ONCE /sd 01/01/2026 /st 00:00 /ru Zima /it /f'
    )
    stdin, stdout, stderr = ssh.exec_command(task_cmd)
    stdout.channel.recv_exit_status()

    # 4. 强行立即触发运行它
    print("[*] 正在启动 Zima 桌面诊断探针...")
    ssh.exec_command('schtasks /run /tn "ZimaDiag"')
    
    # 探针不包含监听死循环，执行完毕仅需 3 秒
    print("[*] 正在等待 Zima 扫描微信窗口树并输出报告 (等待 5 秒)...")
    time.sleep(5)

    # 5. 通过 SSH 读取并打印诊断文件 (此时文件已关闭，绝对无锁)
    print("[*] 正在拉取 Zima 诊断报告...")
    stdin, stdout, stderr = ssh.exec_command('cmd.exe /c "type C:\\wxbot\\diagnose.txt"')
    report = stdout.read().decode('utf-8', errors='ignore')
    
    print("\n================= ZIMA 微信 UIA 诊断报告 =================")
    if report.strip():
        print(report.strip())
    else:
        print("[!] 错误：未能获取到诊断报告。请确认 Zima 上微信是否在桌面上点开。")
    print("==========================================================")

    # 6. 清理临时任务，恢复环境
    print("\n[*] 正在清理 Zima 上的临时任务...")
    ssh.exec_command('schtasks /delete /tn "ZimaDiag" /f')
    ssh.close()

if __name__ == "__main__":
    main()
