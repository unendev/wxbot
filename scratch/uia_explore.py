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
        title = win32gui.GetWindowText(hwnd)
        # 微信的主窗口类名 (自适应 WeChatMainWndForPC 和 Qt51514QWindowIcon)
        if class_name in ["WeChatMainWndForPC", "Qt51514QWindowIcon"]:
            hwnds.append(hwnd)
        return True
    win32gui.EnumWindows(enum_callback, None)
    return hwnds[0] if hwnds else None

def main():
    hwnd = get_wechat_hwnd()
    if not hwnd:
        print("[X] 错误：主力机上未发现运行中的微信 4.0 窗口！请确保小号微信已登录且主界面未最小化。")
        return
        
    print(f"[+] 成功定位主力机微信 HWND: {hwnd} ({hex(hwnd)})")
    
    # 强制向系统广播无障碍唤醒标志
    import ctypes
    ctypes.windll.user32.SystemParametersInfoW(0x0047, True, 0, 0)
    
    # 绑定微信主控件
    ctrl = auto.ControlFromHandle(hwnd)
    if not ctrl:
        print("[X] 绑定 UIA 控件失败。")
        return
        
    print("[*] 正在扫描微信主界面 UIA 结构，寻找聊天消息列表和聊天记录特征...")
    
    # 1. 尝试寻找右侧的聊天记录列表
    # 微信4.0的右侧聊天信息流通常是一个 ListControl，Name 为 "消息"
    message_list = ctrl.ListControl(searchDepth=25, Name="消息")
    if message_list.Exists(0.5):
        print(f"[√] 发现聊天消息流 ListControl (Name: '消息')")
        children = message_list.GetChildren()
        print(f"    - 当前可见消息条数: {len(children)}")
        
        # 遍历消息，寻找含有“的聊天记录”的合并气泡
        found_any = False
        for idx, msg in enumerate(children):
            # 打印前 5 条消息的类型和名称，让我们知道微信4.0的消息控件长啥样
            name_clean = msg.Name.replace('\n', ' ') if msg.Name else 'None'
            print(f"      [{idx}] ClassName: {msg.ClassName}, Name: '{name_clean}', ControlType: {msg.ControlTypeName}")
            
            # 特征匹配合并聊天记录：一般叫 “xxx的聊天记录”
            if msg.Name and ("的聊天记录" in msg.Name or "聊天记录" in msg.Name):
                print(f"      [!] 发现合并聊天记录气泡！索引: {idx}, 标题: '{msg.Name}'")
                found_any = True
                
        if not found_any:
            print("    [-] 当前可见的消息列表中未发现“的聊天记录”气泡。")
    else:
        print("    [-] 未在主界面找到 Name 为 '消息' 的 ListControl 控件。")
        
    # 2. 尝试寻找右上角的“聊天信息”（三个点）按钮
    # 微信4.0的聊天信息按钮在右上角，ClassName 通常是 "mmui::Button"
    # 我们遍历所有的 ButtonControl，打印出它们的 Name，让我们看看哪个是三个点
    buttons = ctrl.ButtonControl(searchDepth=15)
    if buttons.Exists(0.5):
        print("\n[*] 正在扫描主界面按钮...")
        all_buttons = ctrl.GetChildren()
        # 我们来看看右上角有没有聊天信息按钮
        chat_info_btn = ctrl.ButtonControl(searchDepth=15, Name="聊天信息")
        if chat_info_btn.Exists(0.2):
            print(f"[√] 成功定位右上角 '聊天信息 (三个点)' 按钮！")
        else:
            # 打印前几个按钮的名字，便于定位
            btn_list = []
            def walk_buttons(element, depth):
                if depth > 10: return
                for child in element.GetChildren():
                    if "Button" in child.ControlTypeName:
                        btn_list.append(f"Button - Name: '{child.Name}', ClassName: {child.ClassName}")
                    walk_buttons(child, depth + 1)
            walk_buttons(ctrl, 0)
            print(f"    - 扫描到 {len(btn_list)} 个按钮。")
            for btn in btn_list[:15]:
                print(f"      {btn}")

if __name__ == "__main__":
    main()
