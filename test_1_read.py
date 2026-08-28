# -*- coding: utf-8 -*-
"""
第 1 步独立验证脚本：全能窗口定位与消息实时读取
"""
import time
import sys
import ctypes
import uiautomation as auto
import win32gui

# 设置控制台输出编码
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 1. 激活无障碍
SPI_SETSCREENREADER = 0x0046
ctypes.windll.user32.SystemParametersInfoW(SPI_SETSCREENREADER, 1, 0, 1)

print("=" * 50)
print(" [*] 第 1 步测试：全能寻找微信窗口...")
print("=" * 50)

# 2. 全能查找微信 HWND (Win32 + UIA 双通道)
found_hwnd = None
found_title = ""
found_class = ""

def enum_cb(hwnd, _):
    global found_hwnd, found_title, found_class
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        # 匹配类名包含 Qt / WeChat 或标题包含 微信
        if "WeChat" in cls or "Qt" in cls or "微信" in title:
            # 过滤掉极小的隐藏托盘窗口
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w > 300 and h > 300:
                found_hwnd = hwnd
                found_title = title
                found_class = cls
                return False
    return True

try:
    win32gui.EnumWindows(enum_cb, None)
except Exception:
    pass

if not found_hwnd:
    # 备用方案：UIA 遍历桌面
    for win in auto.GetRootControl().GetChildren():
        c_name = win.Name or ""
        c_cls = win.ClassName or ""
        if ("微信" in c_name or "Qt" in c_cls or "WeChat" in c_cls) and win.BoundingRectangle.width() > 300:
            found_hwnd = win.NativeWindowHandle
            found_title = c_name
            found_class = c_cls
            break

if not found_hwnd:
    print("[-] 未在桌面找到可见的微信主窗口，请确保微信未最小化到托盘！")
    sys.exit(1)

print(f"[+] 成功锁定微信窗口！")
print(f"    - HWND 句柄: {found_hwnd}")
print(f"    - 窗口类名: {found_class}")
print(f"    - 窗口标题: {found_title}")

wechat_win = auto.ControlFromHandle(found_hwnd)

# 3. 定位右侧聊天消息列表
msg_list = None
wnd_rect = wechat_win.BoundingRectangle

# 遍历寻找右半区的 ListControl
for child in wechat_win.GetChildren():
    if child.ControlTypeName == "ListControl":
        if child.BoundingRectangle.left > (wnd_rect.left + 150):
            msg_list = child
            break

if not msg_list:
    msg_list = wechat_win.ListControl(searchDepth=25)

if not msg_list or not msg_list.Exists(0.5):
    print("[-] 未定位到右侧聊天消息流，请确认右侧已打开某个聊天！")
    sys.exit(1)

print("[+] 成功定位聊天消息流容器！")
print("[*] 开始实时监听... (请在微信里发一句话，看下方是否实时打印)")
print("-" * 50)

last_seen_msg = None

try:
    while True:
        children = msg_list.GetChildren()
        if children:
            latest_item = children[-1]
            text = latest_item.Name.strip() if latest_item.Name else ""
            
            if text:
                item_rect = latest_item.BoundingRectangle
                list_rect = msg_list.BoundingRectangle
                
                # 判定身份：右边缘靠近列表右边界的是自己，否则是对方
                is_me = item_rect.right >= (list_rect.right - 95)
                sender = "【自己发的】" if is_me else "【对方发的】"
                
                current_tag = f"{sender}: {text}"
                
                if current_tag != last_seen_msg:
                    now_str = time.strftime("%H:%M:%S")
                    print(f"[{now_str}] 实时捕获 -> {sender}: {text}")
                    last_seen_msg = current_tag
                    
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\n[*] 测试已安全停止。")
