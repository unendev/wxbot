# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)

sftp = client.open_sftp()
test_ctypes_py = """# -*- coding: utf-8 -*-
import ctypes
from ctypes import wintypes
import uiautomation as auto

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32 = ctypes.windll.user32

found = []
def enum_windows_callback(hwnd, lparam):
    if user32.IsWindowVisible(hwnd):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            
            cls_buff = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buff, 256)
            cls_name = cls_buff.value
            
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w > 100 and h > 100:
                found.append((hwnd, title, cls_name, (rect.left, rect.top, w, h)))
    return True

cb = WNDENUMPROC(enum_windows_callback)
user32.EnumWindows(cb, 0)

print(f"Total windows found with ctypes: {len(found)}")
for h, t, c, r in found:
    print(f"HWND: {h} | Title: '{t}' | Class: '{c}' | Rect: {r}")
"""
with sftp.file("Desktop/wxbot/test_ctypes.py", "w") as f:
    f.write(test_ctypes_py.encode('utf-8'))
sftp.close()

stdin, stdout, stderr = client.exec_command('cmd.exe /c "chcp 65001 >nul & set PYTHONIOENCODING=utf-8 & cd /d C:\\Users\\zima\\Desktop\\wxbot & uv.exe run python test_ctypes.py"')
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')

print("OUT:\n", out.strip())
if err: print("ERR:\n", err.strip())

client.close()
