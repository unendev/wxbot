# -*- coding: utf-8 -*-
import win32gui

def main():
    print("=== Scanning all open Windows containing 'WeChat' or '微信' ===")
    found = []
    
    def enum_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            # 只要包含微信相关的字眼就记录
            if "wechat" in title.lower() or "微信" in title or "wechat" in class_name.lower() or "mmui" in class_name.lower():
                found.append((hwnd, class_name, title))
        return True
        
    win32gui.EnumWindows(enum_callback, None)
    
    if not found:
        print("[-] 未在当前桌面找到任何匹配 'WeChat' 或 '微信' 属性的可见窗口！")
        # 顺便把前 30 个可见窗口都列一下，看看系统有什么窗口
        print("\n--- 当前桌面可见窗口前 30 个列表 ---")
        visible_wins = []
        def enum_all(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                if title.strip():
                    visible_wins.append((hwnd, class_name, title))
            return True
        win32gui.EnumWindows(enum_all, None)
        for h, c, t in visible_wins[:30]:
            print(f"HWND {h} ({hex(h)}) | ClassName: {c} | Title: '{t}'")
    else:
        for hwnd, class_name, title in found:
            print(f"[√] HWND {hwnd} ({hex(hwnd)}) | ClassName: '{class_name}' | Title: '{title}'")

if __name__ == "__main__":
    main()
