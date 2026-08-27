# -*- coding: utf-8 -*-
import os
import sys
import time
import sqlite3
import requests
import win32gui
import win32con
import uiautomation as auto
import xml.etree.ElementTree as ET
from datetime import datetime

# 强行重新配置 stdout 的编码为 utf-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 日志持久化
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

# ==================== 配置 ====================
TARGET_GROUP = "大丑"
TARGET_ALERT_RECEIVER = "yuaotian"
LLM_API_URL = "http://127.0.0.1:7860/v1/chat/completions"
LLM_API_KEY = "123456"
LLM_MODEL = "gemini-2.5-flash"
# ==============================================

class OrderRepository:
    def __init__(self, db_path="processed_orders.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_orders (
                    id TEXT PRIMARY KEY,
                    timestamp REAL
                )
            """)

    def is_processed(self, order_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT 1 FROM processed_orders WHERE id = ?", (order_id,))
            return cursor.fetchone() is not None

    def mark_as_processed(self, order_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO processed_orders (id, timestamp) VALUES (?, ?)",
                         (order_id, time.time()))

    def clear_all(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM processed_orders")

class WeChatUI:
    def __init__(self):
        self.main_hwnd = None
        self.main_ctrl = None

    def bind_main_window(self):
        hwnds = []
        def enum_callback(hwnd, extra):
            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            if class_name in ["WeChatMainWndForPC", "Qt51514QWindowIcon"] and title == "微信":
                hwnds.append(hwnd)
            return True
        win32gui.EnumWindows(enum_callback, None)

        if hwnds:
            self.main_hwnd = hwnds[0]
            # 激活窗口但不强制置顶，利用 UIA 模式操作
            win32gui.ShowWindow(self.main_hwnd, win32con.SW_SHOWNOACTIVATE)
            self.main_ctrl = auto.WindowControl(searchDepth=1, ClassName="WeChatMainWndForPC")
            if not self.main_ctrl.Exists(0):
                 self.main_ctrl = auto.WindowControl(searchDepth=1, ClassName="Qt51514QWindowIcon")
            return True
        return False

    def find_session(self, name):
        search_edit = self.main_ctrl.EditControl(Name="搜索")
        if search_edit.Exists(2):
            # 使用更稳健的点击和发送按键
            search_edit.Click(simulateMove=False)
            search_edit.SendKeys(name + "{Enter}")
            time.sleep(1)
            return True
        return False

    def get_messages(self):
        message_list = self.main_ctrl.ListControl(Name="消息")
        if message_list.Exists(2):
            return message_list.GetChildren()
        return []

    def send_text(self, receiver, content):
        if self.find_session(receiver):
            input_field = self.main_ctrl.EditControl(Name="输入")
            if input_field.Exists(2):
                input_field.GetValuePattern().SetValue(content)
                input_field.SendKeys("{Enter}")
                return True
        return False

class OrderProcessor:
    def __init__(self, repo, ui, api_url, api_key):
        self.repo = repo
        self.ui = ui
        self.api_url = api_url
        self.api_key = api_key

    def process_new_messages(self):
        if not self.ui.bind_main_window():
            print("[-] 未发现微信窗口")
            return

        if not self.ui.find_session(TARGET_GROUP):
            print(f"[-] 未找到群聊: {TARGET_GROUP}")
            return

        messages = self.ui.get_messages()
        new_packages = []
        for msg in messages:
            if msg.Name and ("的聊天记录" in msg.Name or "聊天记录" in msg.Name):
                msg_id = msg.Name.replace('\n', '').replace(' ', '')
                if not self.repo.is_processed(msg_id):
                    new_packages.append((msg, msg_id))

        print(f"[+] 发现新聊天包: {len(new_packages)}")
        for pkg_ctrl, msg_id in new_packages:
            self._handle_package(pkg_ctrl, msg_id)

    def _handle_package(self, pkg_ctrl, msg_id):
        # 实际生产中这里应包含更复杂的详情页提取逻辑
        # 目前先实现核心框架逻辑
        print(f"[*] 处理消息包: {pkg_ctrl.Name[:30]}...")
        # 模拟 AI 分析 (此处简化，实际应调用 DispatchBrain)
        # analysis = self.brain.analyze(...)
        # self.ui.send_text(TARGET_ALERT_RECEIVER, analysis)
        self.repo.mark_as_processed(msg_id)

def main():
    repo = OrderRepository()
    ui = WeChatUI()
    processor = OrderProcessor(repo, ui, LLM_API_URL, LLM_API_KEY)

    print("[*] 微信自动化助手已启动 (重构版)")
    # 第一次运行可以清理数据库
    # repo.clear_all()

    while True:
        try:
            processor.process_new_messages()
        except Exception as e:
            print(f"[!] 运行异常: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()
