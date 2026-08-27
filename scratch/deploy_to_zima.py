# -*- coding: utf-8 -*-
import sys
import os
import time
import paramiko

ZIMA_IP = "192.168.50.109"
ZIMA_USER = "Zima"
REMOTE_DIR = "C:/wxbot"

# 本地待上传的文件列表 (只传输核心代码，排除 .venv 和大临时文件)
FILES_TO_DEPLOY = [
    "bot.py",
    "start_bot.bat",
    "ZIMABOARD_DEPLOY.md",
]

def main():
    # 获取本地私钥
    private_key_path = os.path.expanduser("~/.ssh/id_ed25519")
    if not os.path.exists(private_key_path):
        print(f"[X] 错误：本地未找到 SSH 私钥: {private_key_path}")
        return
        
    print(f"[*] 正在通过免密密钥连接到 Zima ({ZIMA_IP})...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        key = paramiko.Ed25519Key.from_private_key_file(private_key_path)
        ssh.connect(ZIMA_IP, username=ZIMA_USER, pkey=key, timeout=10)
        print("[+] 局域网 SSH 免密管道握手成功！")
    except Exception as e:
        print(f"[X] 连接失败: {e}")
        return
        
    try:
        sftp = ssh.open_sftp()
        
        # 1. 确保远程 D 盘根目录下 wxbot 文件夹存在
        print(f"[*] 正在 Zima 上创建远程部署工作目录: {REMOTE_DIR}...")
        try:
            sftp.mkdir(REMOTE_DIR)
        except Exception:
            pass
        try:
            sftp.mkdir(f"{REMOTE_DIR}/scratch")
        except Exception:
            pass
            
        # 2. 逐一上传核心代码
        for filename in FILES_TO_DEPLOY:
            local_path = os.path.join(os.getcwd(), filename)
            remote_path = f"{REMOTE_DIR}/{filename}"
            if os.path.exists(local_path):
                print(f"    - 正在上传 {filename} -> {remote_path}...")
                sftp.put(local_path, remote_path)
            else:
                print(f"    [!] 警告：本地未找到文件: {filename}，跳过。")
                
        # 顺便把生成的测试表情包也传过去，省去 Zima 首次生成失败的风险
        test_meme = "scratch/test_meme.png"
        if os.path.exists(test_meme):
            print(f"    - 正在上传 {test_meme}...")
            try:
                sftp.put(test_meme, f"{REMOTE_DIR}/{test_meme}")
            except Exception:
                pass
                
        sftp.close()
        print("[+] 代码包上传部署成功完成！")
        
    except Exception as err:
        print(f"[X] 部署文件传输过程中失败: {err}")
        ssh.close()
        return
        
    # 3. 远程执行命令：初始化虚拟环境并安装依赖
    print("[*] 正在 Zima 远程端建立 Python 虚拟环境 (这需要大约 10-30 秒，请耐心等待)...")
    venv_cmd = f'powershell -Command "if (!(Test-Path {REMOTE_DIR}/.venv)) {{ python -m venv {REMOTE_DIR}/.venv }}"'
    stdin, stdout, stderr = ssh.exec_command(venv_cmd)
    
    # 等待虚拟环境建完
    stdout.channel.recv_exit_status()
    print("[+] 远程虚拟环境初始化完毕！")
    
    print("[*] 正在 Zima 远程端为虚拟环境安装运行依赖 (Pillow, pywin32, psutil, uiautomation, requests)...")
    pip_cmd = f'{REMOTE_DIR}/.venv/Scripts/pip.exe install Pillow pywin32 psutil uiautomation requests'
    stdin, stdout, stderr = ssh.exec_command(pip_cmd)
    
    # 打印远程 pip 安装输出
    exit_status = stdout.channel.recv_exit_status()
    print(stdout.read().decode('utf-8', errors='ignore'))
    print(stderr.read().decode('utf-8', errors='ignore'))
    
    if exit_status == 0:
        print("[√] 远程依赖安装大获全胜！")
        print(f"\n==========================================================")
        print(f"            微信机器人局域网远程一键部署完毕 ")
        print(f"==========================================================")
        print(f"  - 部署目录: Zimaboard 上的 {REMOTE_DIR}")
        print(f"  - 运行方式: 远程打开 {REMOTE_DIR}/start_bot.bat")
        print(f"==========================================================")
    else:
        print("[X] 远程依赖安装失败，请检查 Zima 上 Python 或网络状态！")
        
    ssh.close()

if __name__ == "__main__":
    main()
