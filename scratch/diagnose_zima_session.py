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

    print(f"[*] 连接 Zima ({ZIMA_IP})...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        key = paramiko.Ed25519Key.from_private_key_file(private_key_path)
        ssh.connect(ZIMA_IP, username=ZIMA_USER, pkey=key, timeout=10)
        print("[+] SSH 连接成功！")
    except Exception as e:
        print(f"[X] 连接失败: {e}")
        return

    # 1. 确保清空 Zima 本地先前的 bot.log 并杀掉冲突的任务
    print("[*] 正在远程清理先前的诊断任务与残留进程...")
    ssh.exec_command('schtasks /delete /tn "ZimaBotTest" /f')
    ssh.exec_command('taskkill /f /im python.exe')
    ssh.exec_command('cmd.exe /c "del /q C:\\wxbot\\bot.log"')
    time.sleep(1)

    # 2. 用 schtasks 创建一个带 /it 交互标志的计划任务，注入当前活跃桌面 Session 运行
    print("[*] 正在远程注册交互式 Session 注入探针任务 (schtasks)...")
    # 这里我们重定向输出到 C:\wxbot\bot.log
    task_cmd = (
        'schtasks /create /tn "ZimaBotTest" '
        '/tr "cmd.exe /c C:\\wxbot\\.venv\\Scripts\\python.exe -u C:\\wxbot\\bot.py > C:\\wxbot\\bot.log 2>&1" '
        '/sc ONCE /sd 01/01/2026 /st 00:00 /ru Zima /it /f'
    )
    
    stdin, stdout, stderr = ssh.exec_command(task_cmd)
    res_err = stderr.read().decode('utf-8', errors='ignore')
    if res_err and "成功创建" not in res_err and "SUCCESS" not in res_err:
        print(f"[-] 注册计划任务时可能存在警告: {res_err.strip()}")
    else:
        print("[+] 诊断探针任务已成功注册！")

    # 3. 强行立即触发运行它
    print("[*] 正在强制触发探针运行...")
    ssh.exec_command('schtasks /run /tn "ZimaBotTest"')
    
    # 给它 6 秒的运行绑定时间
    print("[*] 探针正在 Zima 桌面中抓取微信句柄，等待 6 秒...")
    time.sleep(6)

    # 4. 利用 PowerShell 的 .NET 共享流，强制跨越 Windows 写锁读取 bot.log！
    print("[*] 正在突破 Windows 文件锁，远程读取探针实时输出...")
    read_log_cmd = (
        'powershell -Command "'
        '$stream = [System.IO.File]::Open(\'C:\\wxbot\\bot.log\', [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite);'
        '$reader = New-Object System.IO.StreamReader($stream);'
        '$text = $reader.ReadToEnd();'
        '$reader.Close();'
        '$stream.Close();'
        'Write-Output $text;'
        '"'
    )
    
    stdin, stdout, stderr = ssh.exec_command(read_log_cmd)
    log_content = stdout.read().decode('utf-8', errors='ignore')
    log_err = stderr.read().decode('utf-8', errors='ignore')
    
    print("\n================= ZIMA 诊断实时日志 =================")
    if log_content.strip():
        print(log_content.strip())
    else:
        print("[!] 警告：诊断日志内容为空，探针可能未能成功写入。")
        if log_err:
            print(f"[错误反馈] {log_err}")
    print("=====================================================")

    # 5. 安全清理临时任务，保持系统干净
    print("\n[*] 正在清理临时诊断任务，恢复干净挂机环境...")
    ssh.exec_command('schtasks /delete /tn "ZimaBotTest" /f')
    ssh.exec_command('taskkill /f /im python.exe')
    ssh.close()

if __name__ == "__main__":
    main()
