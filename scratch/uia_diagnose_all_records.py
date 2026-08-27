# -*- coding: utf-8 -*-
import sys
import os
import time
import win32gui
import win32con
import uiautomation as auto

def get_wechat_hwnd():
    hwnds = []
    def enum_callback(hwnd, extra):
        class_name = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)
        if class_name in ["WeChatMainWndForPC", "Qt51514QWindowIcon"] and title == "微信":
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
    # 强制清理之前可能残留的微信详情子弹窗，保证测试窗口差集比对能成功
    print("[*] 正在远程清理先前残留的微信详情弹窗...")
    def cleanup_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            if class_name in ["WeChatMainWndForPC", "Qt51514QWindowIcon"] and title != "微信" and title != "":
                print(f"    - 正在强制关闭残留子窗口: '{title}' ({hex(hwnd)})")
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        return True
    win32gui.EnumWindows(cleanup_callback, None)
    time.sleep(1.0)

    hwnd = get_wechat_hwnd()
    if not hwnd:
        print("[X] 错误：未发现微信窗口。")
        return
        
    print(f"[+] 绑定微信 HWND: {hwnd} ({hex(hwnd)})")
    
    # 强制唤醒 UIA
    import ctypes
    ctypes.windll.user32.SystemParametersInfoW(0x0047, True, 0, 0)
    
    ctrl = auto.ControlFromHandle(hwnd)
    if not ctrl:
        print("[X] UIA 绑定失败")
        return
        
    message_list = ctrl.ListControl(searchDepth=25, Name="消息")
    if not message_list.Exists(0.5):
        print("[X] 未发现消息流")
        return
        
    # 物理控制：自动将鼠标移入消息流中心，并向上滚动鼠标滚轮，翻出历史消息气泡
    print("[*] 正在物理模拟向上滚动鼠标滚轮，追溯历史消息...")
    try:
        list_rect = message_list.BoundingRectangle
        center_x = (list_rect.left + list_rect.right) // 2
        center_y = (list_rect.top + list_rect.bottom) // 2
        import win32api
        win32api.SetCursorPos((center_x, center_y))
        time.sleep(0.2)
        # 向上滚动滚轮 2 次，每次滚动 5 个刻度
        message_list.WheelUp(wheelTimes=5)
        time.sleep(1.0)
        message_list.WheelUp(wheelTimes=5)
        time.sleep(1.0)
    except Exception as scroll_err:
        print(f"[-] 自动滚动滚轮失败: {scroll_err}")
        
    children = message_list.GetChildren()
    bubbles = []
    
    # 找出所有包含“聊天记录”的可见气泡
    for msg in children:
        if msg.Name and ("的聊天记录" in msg.Name or "聊天记录" in msg.Name):
            bubbles.append(msg)
            
    print(f"[+] 发现当前屏幕上共有 {len(bubbles)} 个可见的“合并聊天记录”卡片。")
    
    import win32api
    for b_idx, bubble in enumerate(bubbles):
        b_name_clean = bubble.Name.replace('\n', ' ')
        print(f"\n========================================================")
        print(f" [*] 准备诊断第 {b_idx} 个合并聊天卡片: '{b_name_clean}'")
        print(f"========================================================")
        
        rect = bubble.BoundingRectangle
        x = (rect.left + rect.right) // 2
        y = (rect.top + rect.bottom) // 2
        print(f"    - 气泡物理中心坐标: ({x}, {y})")
        
        # 记录双击前的窗口
        wins_before = get_all_active_windows()
        
        # 执行物理双击
        win32api.SetCursorPos((x, y))
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        
        print("    - 正在等待详情窗口加载 (等待 3 秒)...")
        time.sleep(3)
        
        # 获取新弹窗
        wins_after = get_all_active_windows()
        new_wins = []
        before_hwnds = {w[0] for w in wins_before}
        for w in wins_after:
            if w[0] not in before_hwnds:
                new_wins.append(w)
                
        if not new_wins:
            print("    [-] 未检测到新弹出的详情页窗口，跳过该项。")
            continue
            
        popup_hwnd, class_name, title = new_wins[0]
        print(f"    [√] 新详情窗口 HWND {popup_hwnd} ({hex(popup_hwnd)}) | Title: '{title}'")
        
        # 递归探测详情弹窗内部控件树
        try:
            sub_ctrl = auto.ControlFromHandle(popup_hwnd)
            sub_list = sub_ctrl.ListControl(searchDepth=15)
            if sub_list.Exists(1.0):
                items = sub_list.GetChildren()
                print(f"    [√] 成功绑定内部消息流，共有 {len(items)} 条可见消息：")
                
                for idx, item in enumerate(items):
                    item_name = item.Name.replace('\n', ' ') if item.Name else 'None'
                    print(f"      [{idx}] Cell ClassName: '{item.ClassName}' | Name: '{item_name}'")
                    
                    # 递归遍历 Cell 子孙，寻找按钮、附件大小等描述
                    def walk_cell(elem, depth):
                        indent = " " * (8 + depth * 2)
                        for child in elem.GetChildren():
                            c_name = child.Name.replace('\n', ' ') if child.Name else 'None'
                            # 过滤掉过多无意义的空元素展示，聚焦高价值信息
                            if child.Name or child.ControlTypeName in ["ButtonControl", "ImageControl", "TextControl"]:
                                print(f"{indent}* [{child.ControlTypeName}] ClassName: '{child.ClassName}' | Name: '{c_name}'")
                            
                            # 核心：高亮标记潜在的文件动作/图片特征
                            if "file" in child.ClassName.lower() or c_name in ["下载", "打开", "已下载", "查看"] or "Button" in child.ControlTypeName:
                                print(f"{indent}  🔥 [ACTION TARGET] ControlType: {child.ControlTypeName} | ClassName: '{child.ClassName}' | Name: '{c_name}' | Rect: {child.BoundingRectangle}")
                                
                            walk_cell(child, depth + 1)
                            
                    walk_cell(item, 0)
            else:
                print("    [-] 未能在详情窗口中找到滚动 ListControl。")
        except Exception as e:
            print(f"    [X] 探测控件树异常: {e}")
            
        # 诊断完成，远程强行关闭该临时详情窗口，防止桌面堆积
        print(f"    [*] 正在自动关闭该详情窗口 HWND {popup_hwnd}...")
        win32gui.PostMessage(popup_hwnd, win32con.WM_CLOSE, 0, 0)
        time.sleep(1.5)

    print("\n========================================================")
    print(" 批量多卡片多媒体诊断测试全部成功完成！")
    print("========================================================")

if __name__ == "__main__":
    main()
