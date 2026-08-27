# -*- coding: utf-8 -*-
import time
import uiautomation as auto
import win32gui

def get_wechat_hwnds():
    hwnds = []
    def enum_callback(hwnd, extra):
        class_name = win32gui.GetClassName(hwnd)
        if class_name == "Qt51514QWindowIcon":
            hwnds.append(hwnd)
        return True
    win32gui.EnumWindows(enum_callback, None)
    return hwnds

def dump_node(control, depth=0, max_lines=150):
    if depth > 10:
        return
    try:
        name = control.Name
        class_name = control.ClassName
        if name and len(name.strip()) > 0:
            print(f"{'  ' * depth}- [{control.ControlTypeName}] Name: '{name}' | Class: '{class_name}'")
    except Exception:
        pass
        
    try:
        for child in control.GetChildren():
            dump_node(child, depth + 1)
    except Exception:
        pass

def main():
    # 强制开启全局屏幕阅读器标志，激活微信 Qt 渲染树
    import ctypes
    print("[*] 正在向系统广播开启无障碍 (Screen Reader) 标志...")
    ctypes.windll.user32.SystemParametersInfoW(0x0047, True, 0, 0)
    time.sleep(0.5)

    hwnds = get_wechat_hwnds()
    print(f"发现 {len(hwnds)} 个微信窗口，开始激活并打印节点树中可见的所有 Name...")
    for hwnd in hwnds:
        print(f"\n==================== HWND: {hwnd} ({hex(hwnd)}) ====================")
        try:
            win32gui.ShowWindow(hwnd, 5)  # SW_SHOW (强行将隐藏在托盘的窗口拉回屏幕)
            win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE (将最小化状态还原)
            time.sleep(0.8)  # 等待 Qt 控件树完全重建
            
            ctrl = auto.ControlFromHandle(hwnd)
            dump_node(ctrl)
        except Exception as e:
            print(f"[-] 激活或读取 HWND {hwnd} 失败: {e}")

if __name__ == "__main__":
    main()
