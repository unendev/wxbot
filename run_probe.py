# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=5)

script = """# -*- coding: utf-8 -*-
import win32gui

def enum_cb(hwnd, _):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd).strip()
        cls = win32gui.GetClassName(hwnd)
        if title and any(k in title for k in ["渥奇", "小丑", "大丑", "微信", "WeChat", "Steam"]):
            rect = win32gui.GetWindowRect(hwnd)
            print(f"HWND: {hwnd} | Title: [{title}] | Class: [{cls}] | Rect: {rect}")
    return True

win32gui.EnumWindows(enum_cb, None)
"""

sftp = client.open_sftp()
with sftp.file("Desktop/wxbot/probe_hwnds.py", "w") as f:
    f.write(script.encode('utf-8'))
sftp.close()

stdin, stdout, stderr = client.exec_command('cmd.exe /c "cd /d C:\\Users\\zima\\Desktop\\wxbot && uv.exe run python probe_hwnds.py"')
print("WINDOW LIST ON ZIMA:\n", stdout.read().decode('utf-8', errors='ignore'))

client.close()
