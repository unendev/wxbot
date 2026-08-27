import ctypes
import os
import sys
import psutil

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if __name__ == "__main__":
    print("Python running as admin?", is_admin())
    print("Current PID:", os.getpid())
    print("Current user:", os.getlogin() if hasattr(os, 'getlogin') else "Unknown")
    
    print("\n扫描所有进程 (包含无法获取名称的进程):")
    total = 0
    denied = 0
    wechat_like = []
    for proc in psutil.process_iter():
        total += 1
        try:
            name = proc.name()
            pid = proc.pid
            if "wechat" in name.lower():
                wechat_like.append((pid, name, "Accessible"))
        except psutil.AccessDenied:
            denied += 1
            # 尝试通过别的手段或者记录 PID
            wechat_like.append((proc.pid, "Access Denied", "Inaccessible"))
        except Exception as e:
            pass
            
    print(f"总进程数: {total}, 拒绝访问数 (Admin 权限隔离): {denied}")
    print("发现的疑似微信进程:")
    for pid, name, status in wechat_like:
        print(f"  PID: {pid} | 进程名: {name} | 状态: {status}")
