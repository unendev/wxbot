# -*- coding: utf-8 -*-
import sys
import os
import time
import zipfile
import xml.etree.ElementTree as ET
import win32gui
import win32con
import uiautomation as auto

ZIMA_USER = "a1634"

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

def find_any_new_files():
    """在微信目录下，递归寻找所有文件（过滤系统临时项）并返回其路径与修改时间戳"""
    wechat_dirs = [
        f"C:/Users/{ZIMA_USER}/Documents/WeChat Files",
        f"C:/Users/{ZIMA_USER}/OneDrive/Documents/WeChat Files"
    ]
    
    found = {}
    for wechat_dir in wechat_dirs:
        if os.path.exists(wechat_dir):
            for root, dirs, files in os.walk(wechat_dir):
                # 聚焦到文件落地存储目录
                if "Attachment" in root or "Temp" in root or "FileStorage" in root:
                    for file in files:
                        # 过滤无意义缓存和微信的 DB/dat 配置文件
                        if file.lower().endswith((".docx", ".zip", ".rar", ".pdf", ".xlsx", ".pptx", ".txt")):
                            path = os.path.join(root, file).replace("\\", "/")
                            try:
                                found[path] = os.path.getmtime(path)
                            except Exception:
                                pass
    return found

def read_file_content_native(file_path):
    """原生解压并解析 docx (提取文字) 或 zip (列出内部文件树) 或普通文本"""
    try:
        if file_path.lower().endswith(".zip"):
            with zipfile.ZipFile(file_path) as z:
                namelist = z.namelist()
                safe_names = [name.encode('gbk', errors='ignore').decode('gbk') for name in namelist]
                return "ZIP 包含文件目录树:\n" + "\n".join(safe_names[:30]) # 最多打印30个文件
        elif file_path.lower().endswith(".docx"):
            with zipfile.ZipFile(file_path) as z:
                xml_content = z.read("word/document.xml")
                root = ET.fromstring(xml_content)
                namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                texts = []
                for el in root.findall(".//w:t", namespace):
                    if el.text:
                        texts.append(el.text)
                return "".join(texts)
        elif file_path.lower().endswith((".txt", ".html")):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        else:
            # 比如 PDF、Rar、Excel 等其他二进制，我们返回文件名和大小
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            return f"[非文本文件类型] 格式: {os.path.splitext(file_path)[1]} | 大小: {size_mb:.2f} MB"
    except Exception as e:
        return f"解析文件失败: {e}"

def main():
    hwnd = get_wechat_hwnd()
    if not hwnd:
        print("[X] 错误：未发现微信窗口。")
        return
        
    print(f"[+] 绑定微信 HWND: {hwnd} ({hex(hwnd)})")
    
    # 强制将微信主窗口带入前台，穿透 Windows 焦点防护
    try:
        win32gui.ShowWindow(hwnd, 9)
        time.sleep(0.2)
        ctrl = auto.ControlFromHandle(hwnd)
        rect_main = ctrl.BoundingRectangle
        m_x = (rect_main.left + rect_main.right) // 2
        m_y = (rect_main.top + rect_main.bottom) // 2
        import win32api
        import win32con
        print(f"[*] 正在物理点击激活微信主窗口焦点, 坐标: ({m_x}, {m_y})...")
        win32api.SetCursorPos((m_x, m_y))
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.5)
    except Exception as focus_err:
        print(f"[-] 物理激活焦点失败: {focus_err}")
    
    # 强制清理残留详情子弹窗，保证差集比对干净
    print("[*] 正在清理先前残留的微信详情弹窗...")
    def cleanup_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            if class_name in ["WeChatMainWndForPC", "Qt51514QWindowIcon"] and title != "微信" and title != "":
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        return True
    win32gui.EnumWindows(cleanup_callback, None)
    time.sleep(1.0)
    
    ctrl = auto.ControlFromHandle(hwnd)
    message_list = ctrl.ListControl(searchDepth=25, Name="消息")
    if not message_list.Exists(0.5):
        print("[X] 未发现消息流")
        return
        
    # 物理控制：自动将鼠标移入消息流中心，并向上滚动鼠标滚轮，翻出旧消息卡片
    print("[*] 正在物理模拟向上滚动鼠标滚轮，追溯历史消息...")
    try:
        list_rect = message_list.BoundingRectangle
        center_x = (list_rect.left + list_rect.right) // 2
        center_y = (list_rect.top + list_rect.bottom) // 2
        win32api.SetCursorPos((center_x, center_y))
        time.sleep(0.2)
        message_list.WheelUp(wheelTimes=6)
        time.sleep(1.0)
        message_list.WheelUp(wheelTimes=6)
        time.sleep(1.5) # 重绘缓冲时间
    except Exception as scroll_err:
        print(f"[-] 自动滚动滚轮失败: {scroll_err}")
        
    children = message_list.GetChildren()
    bubbles = []
    for msg in children:
        if msg.Name and ("的聊天记录" in msg.Name or "聊天记录" in msg.Name):
            bubbles.append(msg)
            
    print(f"[+] 发现当前可见的聊天记录卡片数: {len(bubbles)}")
    
    # 1. 扫描双击前的任何文件快照
    print("[*] 正在扫描下载前的本地磁盘文件快照...")
    before_files = find_any_new_files()
    print(f"    - 已建立的本地多媒体/文档库快照数: {len(before_files)}")
    
    success_flag = False
    
    # 2. 依次测试每一个可见的聊天记录卡片，直到成功触发任何文件的下载并拿到内容
    for b_idx, bubble in enumerate(bubbles):
        b_name = bubble.Name.replace('\n', ' ')
        b_name_safe = b_name.encode('gbk', errors='ignore').decode('gbk')
        print(f"\n[*] 正在尝试双击打开卡片 {b_idx}: '{b_name_safe}'")
        
        rect = bubble.BoundingRectangle
        x = (rect.left + rect.right) // 2
        y = (rect.top + rect.bottom) // 2
        
        wins_before = get_all_active_windows()
        
        # 物理双击卡片
        win32api.SetCursorPos((x, y))
        time.sleep(0.15)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.12)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        
        time.sleep(3.0)
        
        wins_after = get_all_active_windows()
        new_wins = [w for w in wins_after if w[0] not in {wb[0] for wb in wins_before}]
        
        if not new_wins:
            print("    [-] 未检测到详情弹窗生成。")
            continue
            
        popup_hwnd, class_name, title = new_wins[0]
        title_safe = title.encode('gbk', errors='ignore').decode('gbk')
        print(f"    [√] 成功弹出详情窗口 HWND {popup_hwnd} | Title: '{title_safe}'")
        
        # 在弹窗内寻找任意文件卡片
        sub_ctrl = auto.ControlFromHandle(popup_hwnd)
        sub_list = sub_ctrl.ListControl(searchDepth=15)
        if not sub_list.Exists(1.0):
            print("    [-] 弹窗内无消息流，关闭。")
            win32gui.PostMessage(popup_hwnd, win32con.WM_CLOSE, 0, 0)
            time.sleep(1.0)
            continue
            
        items = sub_list.GetChildren()
        file_cell = None
        for item in items:
            # 核心策略：匹配任意含有未下载文件特征的项
            if item.Name and any(ext in item.Name for ext in [".zip", ".docx", ".pdf", ".rar", ".xlsx", "文件", "未下载"]):
                file_cell = item
                break
                
        if not file_cell:
            print("    [-] 该弹窗内不包含任何文件卡片，关闭并尝试下一个。")
            win32gui.PostMessage(popup_hwnd, win32con.WM_CLOSE, 0, 0)
            time.sleep(1.0)
            continue
            
        # 3. 找到了文件卡片，执行暴力双击下载！
        f_rect = file_cell.BoundingRectangle
        f_x = (f_rect.left + f_rect.right) // 2
        f_y = (f_rect.top + f_rect.bottom) // 2
        f_name_safe = file_cell.Name.replace('\n', ' ').encode('gbk', errors='ignore').decode('gbk')
        print(f"    [+] 成功锁定文件卡片: '{f_name_safe}' | 坐标: ({f_x}, {f_y})")
        
        print("    [*] 正在物理双击该文件卡片强行触发下载...")
        win32api.SetCursorPos((f_x, f_y))
        time.sleep(0.15)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.12)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        
        # 4. 监视是否有任意新文件产生
        print("    [*] 正在监控本地磁盘微信下载目录是否落地新文件...")
        downloaded_path = None
        for seconds in range(30): # 给最多 15 秒下载时间
            time.sleep(0.5)
            current_files = find_any_new_files()
            # 比对文件快照，找出新出现或者被修改的符合格式的文件
            for path, mtime in current_files.items():
                if path not in before_files or mtime > before_files[path] + 1.0:
                    downloaded_path = path
                    break
            if downloaded_path:
                break
                
        if downloaded_path:
            file_basename = os.path.basename(downloaded_path).encode('gbk', errors='ignore').decode('gbk')
            print(f"\n    [√] 终极物理闭环成功达成！！！文件成功落地到硬盘：\n        -> {downloaded_path}")
            print(f"    [*] 正在原生读取并转译 [{file_basename}] 的原始内容...")
            file_body = read_file_content_native(downloaded_path)
            file_body_safe = file_body.encode('gbk', errors='ignore').decode('gbk')
            print("\n================= 落地文件转译内容 =================")
            print(file_body_safe[:600].strip())
            print("=====================================================")
            success_flag = True
        else:
            print("    [X] 警告：物理点击已发出，但 15 秒内未检测到文件存盘。")
            
        # 清理弹窗
        print("    [*] 正在关闭该详情窗口...")
        win32gui.PostMessage(popup_hwnd, win32con.WM_CLOSE, 0, 0)
        break
        
    if not success_flag:
        print("\n[X] 遍历了所有可见聊天卡片，未能捕获到任何文件下载落地。")

if __name__ == "__main__":
    main()
