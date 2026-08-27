# -*- coding: utf-8 -*-
import sys
import os
import time
import win32gui
import uiautomation as auto

def get_wechat_hwnds():
    hwnds = []
    def enum_callback(hwnd, extra):
        class_name = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)
        if class_name == "WeChatMainWndForPC":
            hwnds.append(hwnd)
        return True
    win32gui.EnumWindows(enum_callback, None)
    return hwnds

def main():
    log_path = "C:/wxbot/diagnose.txt"
    out_lines = []
    
    out_lines.append("=== WeChat RPA Zima Auto-Diagnosis ===")
    out_lines.append(f"Current Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    hwnds = get_wechat_hwnds()
    out_lines.append(f"[*] Found WeChat window count: {len(hwnds)}")
    
    for idx, hwnd in enumerate(hwnds):
        out_lines.append(f"\n--- Checking WeChat HWND {hwnd} ({hex(hwnd)}) ---")
        try:
            # 强制校准屏幕标志，防止UIA未唤醒
            import ctypes
            ctypes.windll.user32.SystemParametersInfoW(0x0047, True, 0, 0)
            
            # 使用 UIA 绑定微信主控件
            ctrl = auto.ControlFromHandle(hwnd)
            if not ctrl:
                out_lines.append("    [-] ControlFromHandle failed")
                continue
                
            # 1. 尝试获取当前的聊天窗口标题 (右侧标题栏)
            # 在微信4.0中，群聊标题通常是一个 TextControl，ClassName 为 "mmui::Label" 或是 "mmui::Text"
            title_labels = ctrl.GetChildren()
            out_lines.append(f"    - Child element count: {len(title_labels)}")
            
            # 2. 遍历左侧会话列表，看看里面有哪些群
            session_list = ctrl.ListControl(searchDepth=25, Name="会话")
            if session_list.Exists(0.5):
                out_lines.append("    [+] Left Session List found!")
                children = session_list.GetChildren()
                out_lines.append(f"    - Session list children count: {len(children)}")
                for c_idx, cell in enumerate(children[:15]):
                    name_clean = cell.Name.replace('\n', ' ') if cell.Name else 'None'
                    out_lines.append(f"      [{c_idx}] ClassName: {cell.ClassName}, Name: '{name_clean}'")
            else:
                out_lines.append("    [-] Left Session List '会话' not found in UIA tree.")
                
        except Exception as e:
            out_lines.append(f"    [X] Error inspecting HWND {hwnd}: {e}")
            
    # 写入诊断结果
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines))
        print("[+] Diagnosis successfully saved to D:/wxbot/diagnose.txt")
    except Exception as err:
        print(f"[X] Failed to save diagnosis: {err}")

if __name__ == "__main__":
    main()
