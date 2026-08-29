# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)

sftp = client.open_sftp()
probe_py = """# -*- coding: utf-8 -*-
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import uiautomation as auto
import win32gui

print("=== 扫描所有窗口 ===")
def enum_cb(hwnd, _):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        if (rect[2] - rect[0]) > 100 and (rect[3] - rect[1]) > 100:
            if "WeChat" in cls or "Qt" in cls or "微信" in title or "Chat" in title:
                print(f"HWND: {hwnd}, Title: '{title}', Class: '{cls}', Rect: {rect}")
    return True

win32gui.EnumWindows(enum_cb, None)
"""
with sftp.file("Desktop/wxbot/probe_ui.py", "w") as f:
    f.write(probe_py.encode('utf-8'))
sftp.close()

stdin, stdout, stderr = client.exec_command('cmd.exe /c "set PYTHONIOENCODING=utf-8 & cd /d C:\\Users\\zima\\Desktop\\wxbot & uv.exe run python probe_ui.py"')
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')

print("OUT:\n", out)
if err: print("ERR:\n", err)

client.close()
