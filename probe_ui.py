# -*- coding: utf-8 -*-
"""
微信 UI 控件树一键探测器 (用于快速诊断微信 4.0 Qt 控件结构)
"""
import sys
import win32gui
import uiautomation as auto

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def probe():
    print("=" * 60)
    print(" 微信 4.0 控件树探针 (UI Probe)")
    print("=" * 60)

    found_hwnd = None
    def enum_cb(hwnd, _):
        nonlocal found_hwnd
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            cls = win32gui.GetClassName(hwnd)
            if ("WeChat" in cls or "Qt" in cls or "微信" in title) and not found_hwnd:
                rect = win32gui.GetWindowRect(hwnd)
                if (rect[2] - rect[0]) > 300 and (rect[3] - rect[1]) > 300:
                    found_hwnd = hwnd
                    return False
        return True

    win32gui.EnumWindows(enum_cb, None)

    if not found_hwnd:
        print("[-] 未在桌面上找到可见的微信窗口！")
        return

    title = win32gui.GetWindowText(found_hwnd)
    cls = win32gui.GetClassName(found_hwnd)
    print(f"[+] 锁定微信窗口: 标题='{title}', 类名='{cls}', HWND={found_hwnd}")

    ctrl = auto.ControlFromHandle(found_hwnd)
    
    # 查找 ListControl
    msg_list = None
    wnd_rect = ctrl.BoundingRectangle
    for child in ctrl.GetChildren():
        if child.ControlTypeName == "ListControl" and child.BoundingRectangle.left > (wnd_rect.left + 80):
            msg_list = child
            break
    if not msg_list:
        msg_list = ctrl.ListControl(searchDepth=25)

    if not msg_list or not msg_list.Exists(0.5):
        print("[-] 未找到消息列表 ListControl")
        return

    children = msg_list.GetChildren()
    print(f"[+] 找到消息列表，当前屏幕共包含 {len(children)} 个气泡控件：\n")
    print(f"{'序号':<4} | {'控件类型':<16} | {'尺寸(WxH)':<12} | {'文本内容 / 属性'}")
    print("-" * 65)

    for i, item in enumerate(children, 1):
        r = item.BoundingRectangle
        w = r.right - r.left
        h = r.bottom - r.top
        name = repr(item.Name) if item.Name else "'' (空文本/纯图片/卡片)"
        sub_info = f"子节点数={len(item.GetChildren())}"
        print(f"[{i:02d}] | {item.ControlTypeName:<16} | {f'{w}x{h}':<12} | {name} ({sub_info})")

    print("=" * 60)

if __name__ == "__main__":
    probe()
