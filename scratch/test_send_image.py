# -*- coding: utf-8 -*-
import sys
import os
import time
from io import BytesIO
from PIL import Image, ImageDraw
import win32gui
import win32process
import win32clipboard
import uiautomation as auto
import psutil

TARGET_GROUP = "大丑"

def create_test_image():
    """动态生成一张带时间戳的测试图片"""
    img = Image.new("RGB", (400, 100), color=(100, 149, 237))  # 矢车菊蓝
    d = ImageDraw.Draw(img)
    d.text((10, 40), f"WeChat Bot Test Meme: {int(time.time())}", fill=(255, 255, 255))
    
    # 转换为 CF_DIB 格式所需的数据 (去掉 14 字节的 BMP 文件头)
    output = BytesIO()
    img.save(output, "BMP")
    data = output.getvalue()[14:]
    output.close()
    return data

def backup_clipboard():
    """备份当前剪贴板中的所有可用格式及数据"""
    backup = {}
    win32clipboard.OpenClipboard()
    try:
        fmt = win32clipboard.EnumClipboardFormats(0)
        while fmt:
            try:
                data = win32clipboard.GetClipboardData(fmt)
                backup[fmt] = data
            except Exception:
                pass
            fmt = win32clipboard.EnumClipboardFormats(fmt)
    finally:
        win32clipboard.CloseClipboard()
    return backup

def restore_clipboard(backup):
    """将备份的格式和数据恢复回剪贴板"""
    if not backup:
        return
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        for fmt, data in backup.items():
            try:
                win32clipboard.SetClipboardData(fmt, data)
            except Exception:
                pass
    finally:
        win32clipboard.CloseClipboard()
    print("[+] 成功还原系统剪贴板！")

def set_clipboard_image(data):
    """将 BMP 位图数据写入 Windows 剪贴板"""
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        print("[+] 成功将测试图片写入系统剪贴板！")
    finally:
        win32clipboard.CloseClipboard()

def get_wechat_hwnds():
    """获取所有类名为 Qt51514QWindowIcon 的微信窗口句柄"""
    hwnds = []
    def enum_callback(hwnd, extra):
        class_name = win32gui.GetClassName(hwnd)
        if class_name == "Qt51514QWindowIcon":
            hwnds.append(hwnd)
        return True
    win32gui.EnumWindows(enum_callback, None)
    return hwnds

def find_child_by_name(control, name_keyword, max_depth=15):
    """递归搜索后代控件，匹配 Name 关键字 (避开左侧会话列表项，锁定右侧聊天标题)"""
    if max_depth <= 0:
        return None
    try:
        # 避开左侧会话列表项，防止误判为已点开此会话
        if control.ClassName == "mmui::ChatSessionCell":
            return None
            
        name = control.Name
        if name and name_keyword in name:
            return control
    except Exception:
        pass

    try:
        for child in control.GetChildren():
            res = find_child_by_name(child, name_keyword, max_depth - 1)
            if res:
                return res
    except Exception:
        pass
    return None

def switch_to_group(wechat_ctrl, target_group_name):
    """如果在右侧聊天详情里没有匹配到群，尝试在左侧会话列表中找到目标群并静默点击切换过去"""
    try:
        session_list = wechat_ctrl.ListControl(searchDepth=25, Name="会话")
        if session_list.Exists(0):
            for item in session_list.GetChildren():
                if item.ClassName == "mmui::ChatSessionCell" and target_group_name in item.Name:
                    print(f"[+] 发现左侧会话列表中有目标群聊: '{item.Name.replace('\n', ' ')}'，触发静默双击切换...")
                    item.Click(simulateClick=True)
                    time.sleep(0.8)
                    return True
    except Exception as e:
        print(f"[-] 自动切换会话失败: {e}")
    return False

def bind_wechat_bot(target_group_name):
    """绑定目标微信窗口"""
    hwnds = get_wechat_hwnds()
    if not hwnds:
        print("[-] 未发现运行中且可见的微信 4.0 窗口！")
        return None, None
    print(f"[*] 发现 {len(hwnds)} 个候选微信窗口，正在激活并匹配群聊特征...")
    for hwnd in hwnds:
        try:
            # 强行将窗口恢复并显示，避免因为最小化导致无障碍树闭锁
            win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
            time.sleep(0.5)
            
            ctrl = auto.ControlFromHandle(hwnd)
            matched_ctrl = find_child_by_name(ctrl, target_group_name, max_depth=35)
            if matched_ctrl:
                print(f"[+] 匹配成功！在 HWND {hwnd} ({hex(hwnd)}) 下锁定特征: '{matched_ctrl.Name}'")
                return ctrl, hwnd
            if switch_to_group(ctrl, target_group_name):
                matched_ctrl = find_child_by_name(ctrl, target_group_name, max_depth=35)
                if matched_ctrl:
                    print(f"[+] 自动切换并匹配成功！在 HWND {hwnd} ({hex(hwnd)})锁定特征: '{matched_ctrl.Name}'")
                    return ctrl, hwnd
        except Exception as e:
            print(f"[-] 尝试匹配 HWND {hwnd} 时出错: {e}")
            continue
    return None, None

def main():
    print("[*] 正在准备发送测试...")
    
    # 强制开启全局屏幕阅读器标志，激活微信 Qt 渲染树
    import ctypes
    print("[*] 正在向系统广播开启无障碍 (Screen Reader) 标志...")
    ctypes.windll.user32.SystemParametersInfoW(0x0047, True, 0, 0)
    time.sleep(0.5)
    
    # 1. 寻找并绑定微信窗口
    wechat_ctrl, hwnd = bind_wechat_bot(TARGET_GROUP)
    if not wechat_ctrl:
        print(f"[X] 错误：未能在任何微信窗口中找到正在打开的群聊 '{TARGET_GROUP}' 界面！")
        return
        
    # 2. 定位输入框
    input_box = wechat_ctrl.EditControl(searchDepth=35, ClassName="mmui::ChatInputField")
    if not input_box.Exists(1, 1):
        print("[X] 错误：无法定位到微信聊天输入框！")
        return
        
    print("[+] 成功定位到输入框，准备发送图片...")
    
    # 【核心保护】在写入图片前，备份系统剪贴板中的一切格式数据
    clip_backup = backup_clipboard()
    
    try:
        # 3. 生成并复制图片
        img_data = create_test_image()
        set_clipboard_image(img_data)
        
        # 4. 聚焦输入框并粘贴
        # 激活并显示微信窗口，保证热键可投递
        win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE 恢复并激活
        time.sleep(0.3)
        
        input_box.SetFocus()
        time.sleep(0.2)
        
        print("[*] 发送 Ctrl+V 粘贴快捷键...")
        input_box.SendKeys("{Ctrl}v")
        time.sleep(0.5)
        
        print("[*] 发送 Enter 键 (UIA)...")
        input_box.SendKeys("{Enter}")
        time.sleep(0.3)
        
        print("[*] 发送物理 Enter 键 (win32)...")
        import win32api
        import win32con
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.5)
        
        print("[√] 测试图片已成功发送！")
    finally:
        # 【核心保护】无论发送成功或失败，强制还原系统剪贴板
        restore_clipboard(clip_backup)
    
    print("[√] 测试脚本执行完毕。请在任意地方 Ctrl+V 检查系统剪贴板是否已成功恢复原状！")

if __name__ == "__main__":
    main()
