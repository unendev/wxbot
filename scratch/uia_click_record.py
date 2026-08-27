# -*- coding: utf-8 -*-
import sys
import os
import time
import win32gui
import uiautomation as auto

def get_wechat_hwnd():
    hwnds = []
    def enum_callback(hwnd, extra):
        class_name = win32gui.GetClassName(hwnd)
        if class_name in ["WeChatMainWndForPC", "Qt51514QWindowIcon"]:
            hwnds.append(hwnd)
        return True
    win32gui.EnumWindows(enum_callback, None)
    return hwnds[0] if hwnds else None

def get_all_active_windows():
    wins = []
    def enum_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            wins.append((hwnd, class_name, title))
        return True
    win32gui.EnumWindows(enum_callback, None)
    return wins

def main():
    hwnd = get_wechat_hwnd()
    if not hwnd:
        print("[X] 错误：未发现微信窗口。")
        return
        
    print(f"[+] 绑定微信 HWND: {hwnd} ({hex(hwnd)})")
    
    # 强制激活
    import ctypes
    ctypes.windll.user32.SystemParametersInfoW(0x0047, True, 0, 0)
    
    ctrl = auto.ControlFromHandle(hwnd)
    if not ctrl:
        print("[X] 绑定失败")
        return
        
    message_list = ctrl.ListControl(searchDepth=25, Name="消息")
    if not message_list.Exists(0.5):
        print("[X] 未发现消息流")
        return
        
    children = message_list.GetChildren()
    target_bubble = None
    
    # 寻找第一个合并聊天记录气泡
    for msg in children:
        if msg.Name and ("的聊天记录" in msg.Name or "聊天记录" in msg.Name):
            target_bubble = msg
            break
            
    if not target_bubble:
        print("[-] 消息列表中没有可供点击的“聊天记录”气泡！请确保聊天界面里有聊天记录气泡可见。")
        return
        
    print(f"[+] 找到目标气泡: '{target_bubble.Name.replace('\n', ' ')}'")
    
    # 获取点击前的全部窗口列表
    wins_before = get_all_active_windows()
    
    rect = target_bubble.BoundingRectangle
    x = (rect.left + rect.right) // 2
    y = (rect.top + rect.bottom) // 2
    print(f"[*] 找到气泡卡片的物理中心坐标: ({x}, {y})")
    
    # 使用 win32api 原生的硬件级鼠标移动与双击
    import win32api
    import win32con
    print(f"[*] 正在物理移动鼠标到坐标 ({x}, {y}) 并执行双击...")
    win32api.SetCursorPos((x, y))
    time.sleep(0.1)
    # 第一次单击
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.05)
    # 第二次单击
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        
    print("[*] 已触发点击，等待 2.5 秒让详情弹窗生成...")
    time.sleep(2.5)
    
    # 获取点击后的窗口列表，找出新产生的窗口
    wins_after = get_all_active_windows()
    
    new_wins = []
    before_hwnds = {w[0] for w in wins_before}
    for w in wins_after:
        if w[0] not in before_hwnds:
            new_wins.append(w)
            
    print("\n================ 扫描到新弹出的窗口 ================")
    if not new_wins:
        print("[-] 警告：点击后没有检测到任何新窗口弹出！")
        print("    可能原因：1. 气泡没有被成功双击；2. 详情窗口不是独立句柄。")
    else:
        for h, c, t in new_wins:
            print(f"[√] 新窗口 HWND {h} ({hex(h)}) | ClassName: '{c}' | Title: '{t}'")
            
            # 尝试在这个新弹窗里，探测里面的文字，看看能不能读出历史对话！
            print(f"[*] 正在尝试绑定并探测该新弹窗 [{t}] 内部的 UIA 控件树...")
            try:
                sub_ctrl = auto.ControlFromHandle(h)
                # 遍历弹窗里的列表
                sub_list = sub_ctrl.ListControl(searchDepth=15)
                if sub_list.Exists(1.0):
                    print("    [√] 成功在新窗口里找到会话 ListControl！")
                    sub_children = sub_list.GetChildren()
                    print(f"    - 该弹窗内包含消息条数: {len(sub_children)}")
                    for sc_idx, cell in enumerate(sub_children[:10]):
                        c_name = cell.Name.replace('\n', ' ') if cell.Name else 'None'
                        print(f"      [{sc_idx}] ClassName: {cell.ClassName}, Name: '{c_name}'")
                else:
                    # 遍历打印前 15 个子孙控件，看看有没有文本
                    txt_list = []
                    def walk_tree(element, depth):
                        if depth > 8 or len(txt_list) > 20: return
                        for child in element.GetChildren():
                            if child.Name and child.ControlTypeName in ["TextControl", "ListItemControl"]:
                                txt_list.append(f"{child.ControlTypeName} -> '{child.Name.replace('\n', ' ')}'")
                            walk_tree(child, depth + 1)
                    walk_tree(sub_ctrl, 0)
                    print(f"    - 扫描到子孙控件列表 (前 20 项):")
                    for txt in txt_list:
                        print(f"      {txt}")
            except Exception as exc:
                print(f"    [X] 探测新窗口控件树失败: {exc}")
    print("====================================================")

if __name__ == "__main__":
    main()
