# -*- coding: utf-8 -*-
"""
第 2 步独立验证脚本：精准发送触发
"""
import time
import sys
import ctypes
import uiautomation as auto
import win32gui

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SPI_SETSCREENREADER = 0x0046
ctypes.windll.user32.SystemParametersInfoW(SPI_SETSCREENREADER, 1, 0, 1)

print("=" * 50)
print(" [*] 第 2 步测试：正在定位微信并执行确定性发送...")
print("=" * 50)

found_hwnd = None
def enum_cb(hwnd, _):
    global found_hwnd
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        if "WeChat" in cls or "Qt" in cls or "微信" in title:
            rect = win32gui.GetWindowRect(hwnd)
            if (rect[2] - rect[0]) > 300 and (rect[3] - rect[1]) > 300:
                found_hwnd = hwnd
                return False
    return True

try:
    win32gui.EnumWindows(enum_cb, None)
except Exception:
    pass

if not found_hwnd:
    print("[-] 未找到微信窗口！")
    sys.exit(1)

# 1. 激活微信前台
try:
    win32gui.SetForegroundWindow(found_hwnd)
    time.sleep(0.1)
except Exception:
    pass

wechat_win = auto.ControlFromHandle(found_hwnd)

# 2. 定位输入框
input_box = wechat_win.EditControl(searchDepth=35)
if not input_box.Exists(0.5):
    input_box = wechat_win.EditControl(searchDepth=20)

test_text = "【第2步验证】写入+发送完全成功！"
print(f"[*] 写入文字: {test_text}")

# 内存写入
val_pattern = input_box.GetValuePattern()
if val_pattern:
    val_pattern.SetValue(test_text)
else:
    input_box.SendKeys(test_text)

time.sleep(0.1)

# 3. 确定性发送：点击输入框 -> 按下回车键
print("[*] 正在触发前台回车发送...")
input_box.Click(simulateMove=False)
time.sleep(0.05)
auto.SendKeys("{Enter}")

print("[+] 发送动作已执行！请确认副屏消息是否已发出！")
print("=" * 50)
