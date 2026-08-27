# -*- coding: utf-8 -*-
import os
import re
import sys
import time
import zipfile
import sqlite3
import requests
import win32gui
import win32con
import uiautomation as auto
import xml.etree.ElementTree as ET

# 强行重新配置 stdout 的编码为 utf-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 强制切换工作目录至脚本绝对路径，解决计划任务/开机启动权限丢失问题
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"[+] 已强制校准工作目录至: {script_dir}")
except Exception as e:
    print(f"[-] 强制校准工作目录失败: {e}")

# 日志持久化双写 Logger
class Logger(object):
    def __init__(self, filename="bot.log"):
        self.terminal = sys.stdout
        self.log_path = filename

    def write(self, message):
        self.terminal.write(message)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(message)
        except Exception:
            pass

    def flush(self):
        self.terminal.flush()

sys.stdout = Logger("bot.log")

# ==================== 派单自动化配置 ====================
TARGET_GROUP = "大丑"              # 监听的目标群聊/会话名称
TARGET_ALERT_RECEIVER = "yuaotian"  # 提醒推送的目标好友昵称/微信号/备注名
LLM_API_URL = "http://127.0.0.1:7860/v1/chat/completions"
LLM_API_KEY = "123456"
LLM_MODEL = "gemini-2.5-flash"      # 调用大模型型号
# ========================================================

# 获取当前 Windows 用户名以自适应本地微信下载文件夹路径
CURRENT_USER = os.environ.get("USERNAME") or os.getlogin()

# SQLite 查重初始化
def init_db():
    conn = sqlite3.connect("processed_orders.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS processed_orders (
            id TEXT PRIMARY KEY,
            timestamp REAL
        )
    """)
    conn.commit()
    conn.close()

def is_order_processed(order_id):
    conn = sqlite3.connect("processed_orders.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM processed_orders WHERE id = ?", (order_id,))
    res = c.fetchone()
    conn.close()
    return res is not None

def mark_order_processed(order_id):
    conn = sqlite3.connect("processed_orders.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO processed_orders (id, timestamp) VALUES (?, ?)", (order_id, time.time()))
    conn.commit()
    conn.close()

# 微信主句柄绑定
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

# 递归寻找最新产生的文件
def find_any_new_files():
    wechat_dirs = [
        f"C:/Users/{CURRENT_USER}/Documents/WeChat Files",
        f"C:/Users/{CURRENT_USER}/OneDrive/Documents/WeChat Files"
    ]
    
    found = {}
    for wechat_dir in wechat_dirs:
        if os.path.exists(wechat_dir):
            for root, dirs, files in os.walk(wechat_dir):
                if "Attachment" in root or "Temp" in root or "FileStorage" in root:
                    for file in files:
                        if file.lower().endswith((".docx", ".zip", ".rar", ".pdf", ".xlsx", ".pptx", ".txt")):
                            path = os.path.join(root, file).replace("\\", "/")
                            try:
                                found[path] = os.path.getmtime(path)
                            except Exception:
                                pass
    return found

# 原生解密与转译本地多媒体文件
def read_file_content_native(file_path):
    try:
        if file_path.lower().endswith(".zip"):
            with zipfile.ZipFile(file_path) as z:
                namelist = z.namelist()
                safe_names = [name.encode('gbk', errors='ignore').decode('gbk') for name in namelist]
                return "ZIP 包含文件目录树:\n" + "\n".join(safe_names[:30])
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
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            return f"[非文本文件类型] 格式: {os.path.splitext(file_path)[1]} | 大小: {size_mb:.2f} MB"
    except Exception as e:
        return f"解析文件失败: {e}"

# LLM 决策脑
class DispatchBrain:
    def __init__(self):
        self.system_prompt = """
你是一个专业软件外包派单群的分析助手。
你将收到来自“合并聊天记录”、“Word附件提炼文本”以及“压缩包文件目录树”组合而成的派单高密度转译信息。
请你对这个外包单子进行快速且深度的研判，在 200 字内提炼出结构化简报，并给单子评分。

【研判提炼格式规约】：
🔔【新单研判】
* 简述：[简短描述一句话这是个什么项目]
* 技术栈：[如 Vue3 / FastAPI / Go / 微信小程序]
* 交付期：[如 3天 / 截止到X月X日 / 紧急]
* 预算：[如 500元 / 2k / 暂无]
* 核心需求：1. xxx 2. xxx
* 智能打分：[如 ⭐ 8.5 分 (性价比高，建议接单) 或者是 ⭐ 3.0 分 (需求模糊，预算极低，建议跳过)]

请务必保持格式整齐、排版清晰，无任何多余开场白废话。
"""

    def analyze(self, raw_content):
        try:
            payload = {
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"请分析以下转译订单信息：\n\n{raw_content}"}
                ],
                "temperature": 0.3
            }
            headers = {
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json"
            }
            response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                return f"[AI 研判离线 HTTP {response.status_code}]"
        except Exception as e:
            return f"[AI 研判抛错 {e}]"

brain = DispatchBrain()

# 主物理点击与翻页控制器
def run_history_capture(ctrl):
    message_list = ctrl.ListControl(searchDepth=25, Name="消息")
    if not message_list.Exists(0.5):
        print("[X] 未发现消息流，请确保聊天窗口已点开！")
        return
        
    # 自动物理定位并向上滚动鼠标滚轮以加载历史消息
    print("[*] 正在物理模拟向上滚动鼠标滚轮，追溯历史消息...")
    try:
        list_rect = message_list.BoundingRectangle
        center_x = (list_rect.left + list_rect.right) // 2
        center_y = (list_rect.top + list_rect.bottom) // 2
        import win32api
        import win32con
        win32api.SetCursorPos((center_x, center_y))
        time.sleep(0.2)
        # 单击激活焦点
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.3)
        # 向上滚动滚轮
        message_list.WheelUp(wheelTimes=6)
        time.sleep(1.0)
        message_list.WheelUp(wheelTimes=6)
        time.sleep(1.5)
    except Exception as scroll_err:
        print(f"[-] 自动滚动滚轮失败: {scroll_err}")
        
    children = message_list.GetChildren()
    bubbles = []
    for msg in children:
        if msg.Name and ("的聊天记录" in msg.Name or "聊天记录" in msg.Name):
            # 将卡片 Name 作为去重 Key
            clean_id = msg.Name.replace('\n', '').replace(' ', '')
            if not is_order_processed(clean_id):
                bubbles.append((msg, clean_id))
                
    print(f"[+] 发现未处理的合并聊天包数量: {len(bubbles)}")
    
    # 逐个处理合并聊天记录卡片
    for idx, (bubble, clean_id) in enumerate(bubbles):
        b_name_safe = bubble.Name.replace('\n', ' ').encode('gbk', errors='ignore').decode('gbk')
        print(f"\n========================================================")
        print(f" [*] 正在处理第 {idx} 个未读卡片: '{b_name_safe}'")
        print(f"========================================================")
        
        rect = bubble.BoundingRectangle
        x = (rect.left + rect.right) // 2
        y = (rect.top + rect.bottom) // 2
        
        wins_before = get_all_active_windows()
        
        # 物理双击
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
            print("    [-] 未检测到新详情弹窗产生。")
            continue
            
        popup_hwnd, class_name, title = new_wins[0]
        title_safe = title.encode('gbk', errors='ignore').decode('gbk')
        print(f"    [√] 新详情窗口 HWND {popup_hwnd} | Title: '{title_safe}'")
        
        # 在弹窗内寻找消息流并提取文字和尝试下载文件
        try:
            sub_ctrl = auto.ControlFromHandle(popup_hwnd)
            sub_list = sub_ctrl.ListControl(searchDepth=15)
            if sub_list.Exists(1.5):
                items = sub_list.GetChildren()
                print(f"    - 成功展开详情页消息流，可见子项: {len(items)}")
                
                # 收集弹窗里的文字内容
                texts_collected = []
                file_cell = None
                for item in items:
                    if item.Name:
                        texts_collected.append(item.Name)
                        # 检测是否包含文件
                        if any(ext in item.Name for ext in [".zip", ".docx", ".pdf", ".rar", ".xlsx", "文件", "未下载"]):
                            file_cell = item
                
                texts_raw = "\n".join(texts_collected)
                file_raw_content = ""
                
                # 尝试双击下载文件附件
                if file_cell:
                    f_rect = file_cell.BoundingRectangle
                    f_x = (f_rect.left + f_rect.right) // 2
                    f_y = (f_rect.top + f_rect.bottom) // 2
                    f_name_safe = file_cell.Name.replace('\n', ' ').encode('gbk', errors='ignore').decode('gbk')
                    print(f"    [+] 锁定详情页内文件卡片: '{f_name_safe}' | 坐标: ({f_x}, {f_y})")
                    
                    before_files = find_any_new_files()
                    print("    [*] 物理双击文件触发下载...")
                    win32api.SetCursorPos((f_x, f_y))
                    time.sleep(0.15)
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    time.sleep(0.05)
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    time.sleep(0.12)
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    time.sleep(0.05)
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    
                    # 监控文件落地
                    downloaded_path = None
                    for seconds in range(16): # 等待最多 8 秒下载
                        time.sleep(0.5)
                        current_files = find_any_new_files()
                        for path, mtime in current_files.items():
                            if path not in before_files or mtime > before_files[path] + 1.0:
                                downloaded_path = path
                                break
                        if downloaded_path:
                            break
                            
                    if downloaded_path:
                        print(f"    [√] 文件下载存盘成功: {downloaded_path}")
                        file_raw_content = read_file_content_native(downloaded_path)
                    else:
                        print("    [X] 下载失败或文件已过期。")
                
                # 拼接高密度订单原文
                report_input = f"--- 聊天历史文本 ---\n{texts_raw}\n\n--- 附件文件转译 ---\n{file_raw_content}"
                
                # 送入 AI 研判大脑
                print("    [*] 正在将高密度数据送入大语言模型进行研判...")
                analysis_report = brain.analyze(report_input)
                print("    [√] AI 研判简报生成成功！")
                
                # 将此单私聊发回给大号
                send_alert_to_receiver(ctrl, analysis_report)
                
                # 标记为已消费
                mark_order_processed(clean_id)
            else:
                print("    [-] 详情页内未发现 ListControl 消息滚动树。")
        except Exception as err:
            print(f"    [X] 解析异常: {err}")
            
        # 清理关闭当前子详情页
        print("    [*] 自动清理并关闭该详情页。")
        win32gui.PostMessage(popup_hwnd, win32con.WM_CLOSE, 0, 0)
        time.sleep(1.5)

# 发送私聊强提醒推送给大号
def send_alert_to_receiver(ctrl, report_content):
    print(f"[*] 正在切入大号会话会话 [{TARGET_ALERT_RECEIVER}] 并发送提醒...")
    try:
        # 定位搜索框
        search_edit = ctrl.EditControl(searchDepth=10, Name="搜索")
        if search_edit.Exists(1.0):
            search_edit.Click()
            time.sleep(0.1)
            # 输入大号名字并回车切入会话
            search_edit.SendKeys(TARGET_ALERT_RECEIVER + "{Enter}")
            time.sleep(0.5)
            
            # 定位输入框
            input_field = ctrl.EditControl(searchDepth=20, Name="输入")
            if input_field.Exists(1.0):
                # 内存级直接注入大号会话，不占用用户剪贴板
                input_field.SetValue(report_content)
                time.sleep(0.1)
                input_field.SendKeys("{Enter}")
                print(f"[√] 强提醒已成功推送到大号私聊！")
                time.sleep(0.5)
            else:
                print("[-] 未定位到微信输入框")
        else:
            print("[-] 未定位到微信搜索框，无法切回大号私聊。")
    except Exception as e:
        print(f"[-] 推送强提醒异常: {e}")

# 主巡检守护线程
def main():
    init_db()
    # 调试期间强行清空去重数据库，以便反复测试冷启动追溯小目标！
    try:
        conn = sqlite3.connect("processed_orders.db")
        c = conn.cursor()
        c.execute("DELETE FROM processed_orders")
        conn.commit()
        conn.close()
    except Exception as db_err:
        print(f"[-] 强制清理去重表失败: {db_err}")
    print("[*] 微信派单群自动化转译提醒助手 (V3.0) 已启动。")
    
    hwnd = get_wechat_hwnd()
    if not hwnd:
        print("[X] 错误：未发现微信窗口，请确保微信 4.0 已打开！")
        return
        
    print(f"[+] 成功绑定微信主窗口 HWND: {hwnd} ({hex(hwnd)})")
    
    # 强行物理点击激活主窗口
    try:
        import win32api
        import win32con
        win32gui.ShowWindow(hwnd, 9)
        time.sleep(0.2)
        ctrl = auto.ControlFromHandle(hwnd)
        rect_main = ctrl.BoundingRectangle
        m_x = (rect_main.left + rect_main.right) // 2
        m_y = (rect_main.top + rect_main.bottom) // 2
        win32api.SetCursorPos((m_x, m_y))
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.5)
    except Exception as e:
        print(f"[-] 物理激活主焦点失败: {e}")
        
    ctrl = auto.ControlFromHandle(hwnd)
    
    # 小目标：冷启动时，先全自动向上追溯历史消息，提取并给大号私聊推送
    print("\n>>> 开始执行“冷启动历史派单追溯”小目标任务...")
    run_history_capture(ctrl)
    
    print("\n[√] 历史追溯研判全部执行完毕！程序将自动退出。")

if __name__ == "__main__":
    main()
