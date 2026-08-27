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
    
    # 强行激活
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
        print("[-] 消息列表中没有可供点击的“聊天记录”气泡！请确保当前聊天窗口里显示了含聊天记录的气泡。")
        return
        
    print(f"[+] 找到目标气泡: '{target_bubble.Name.replace('\n', ' ')}'")
    
    rect = target_bubble.BoundingRectangle
    x = (rect.left + rect.right) // 2
    y = (rect.top + rect.bottom) // 2
    print(f"[*] 气泡物理中心坐标: ({x}, {y})")
    
    wins_before = get_all_active_windows()
    
    # 物理鼠标双击
    import win32api
    import win32con
    print("[*] 正在物理双击展开气泡...")
    win32api.SetCursorPos((x, y))
    time.sleep(0.1)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    
    print("[*] 已触发，等待 3.0 秒详情窗口加载...")
    time.sleep(3.0)
    
    wins_after = get_all_active_windows()
    new_wins = []
    before_hwnds = {w[0] for w in wins_before}
    for w in wins_after:
        if w[0] not in before_hwnds:
            new_wins.append(w)
            
    print("\n================ 扫描到新弹出的详情窗口 ================")
    if not new_wins:
        print("[-] 未检测到新弹窗。请确认是否已经打开了详情页。")
        return
        
    popup_hwnd, class_name, title = new_wins[0]
    print(f"[√] 详情窗口 HWND {popup_hwnd} ({hex(popup_hwnd)}) | ClassName: '{class_name}' | Title: '{title}'")
    
    # 深度递归探测子弹窗控件树
    print(f"[*] 正在深度递归扫描 [{title}] 子弹窗，寻找文件附件和图片控件...")
    try:
        sub_ctrl = auto.ControlFromHandle(popup_hwnd)
        sub_list = sub_ctrl.ListControl(searchDepth=15)
        
        if sub_list.Exists(1.0):
            print("    [√] 成功找到详情窗口的滚动消息列表 ListControl")
            items = sub_list.GetChildren()
            print(f"    - 可见消息子条目数: {len(items)}")
            
            for idx, item in enumerate(items):
                item_name = item.Name.replace('\n', ' ') if item.Name else 'None'
                print(f"\n      [{idx}] Message Cell | ClassName: '{item.ClassName}' | Name: '{item_name}'")
                
                # 递归打印出这个 Cell 的所有子孙控件 (找出图片、文件下载按钮等细部特征)
                def walk_cell(elem, depth):
                    indent = " " * (8 + depth * 2)
                    for child in elem.GetChildren():
                        c_name = child.Name.replace('\n', ' ') if child.Name else 'None'
                        print(f"{indent}* [{child.ControlTypeName}] ClassName: '{child.ClassName}' | Name: '{c_name}' | Rect: {child.BoundingRectangle}")
                        
                        # 核心校验：如果发现类似“下载”或“打开”的按钮，打印出提示！
                        if "button" in child.ControlTypeName.lower() or c_name in ["下载", "打开", "已下载", "查看"]:
                            print(f"{indent}  🔥 [FOUND TARGET ACTION BUTTON] Name: '{c_name}', Rect: {child.BoundingRectangle}")
                            
                        # 继续递归
                        walk_cell(child, depth + 1)
                        
                walk_cell(item, 0)
        else:
            print("    [-] 详情窗口内未发现 ListControl 消息流列表。")
            
    except Exception as exc:
        print(f"    [X] 探测控件树抛错: {exc}")
    print("========================================================")

if __name__ == "__main__":
    main()
