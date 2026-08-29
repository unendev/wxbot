# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=5)

test_script = """# -*- coding: utf-8 -*-
import win32gui

def enum_cb(hwnd, _):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd).strip()
        cls = win32gui.GetClassName(hwnd)
        if title:
            rect = win32gui.GetWindowRect(hwnd)
            print(f"HWND: {hwnd} | Title: [{title}] | Class: [{cls}] | Rect: {rect}")
    return True

win32gui.EnumWindows(enum_cb, None)
"""

sftp = client.open_sftp()
with sftp.file("Desktop/wxbot/check_windows_live.py", "w") as f:
    f.write(test_script.encode('utf-8'))
sftp.close()

stdin, stdout, stderr = client.exec_command('cmd.exe /c "cd /d C:\\Users\\zima\\Desktop\\wxbot && uv.exe run python check_windows_live.py"')
print("WINDOWS:\n", stdout.read().decode('utf-8', errors='ignore'))
client.close()
