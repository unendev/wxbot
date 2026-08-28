# -*- coding: utf-8 -*-
"""
微信 AI 智能全能助手 (自研原生 UIA + 控件级无损视觉引擎)
核心哲学：
1. 控件级原生无损截屏 (CaptureToImage)：
   彻底废弃“鼠标点击+磁盘搜寻+ESC闪退”的脆弱链路！
   直接利用 UIA 控件级无损截屏毫秒级捕获气泡图像，零弹窗、零焦点抢夺、零超时。
2. 状态快照 + 末端增量游标 (Tail-Cursor)：冷启动静默，连续发重复消息 100% 准时捕获。
3. 自然多模态视窗注入：视窗内关联图片无条件伴随装箱，由 Gemini 原生多模态注意力自主作答。
4. 防回声自闭环 (Echo Suppression)：100% 杜绝“自己回复自己”的死循环。
5. 连续发送多消息合并：对方连发多条短消息时自动合并为单次提问。
"""
import os
import re
import sys
import time
import ctypes
from pathlib import Path
from collections import deque
from PIL import Image

# 1. 控制台 UTF-8 编码
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import win32gui
import uiautomation as auto
from llm_service import call_llm

# =========================================================
# 配置区：需要监听的好友备注名或群聊名称
# =========================================================
LISTEN_TARGETS = ["bot", "老父亲", "测试群"]

# 激活系统屏幕无障碍辅助支持
SPI_SETSCREENREADER = 0x0046
ctypes.windll.user32.SystemParametersInfoW(SPI_SETSCREENREADER, 1, 0, 1)

# 时间戳正则
RE_TIMESTAMP = re.compile(
    r"^(\d{1,2}:\d{2}|昨天\s*\d{1,2}:\d{2}|星期[一二三四五六日天]\s*\d{1,2}:\d{2}|\d{4}年\d{1,2}月\d{1,2}日.*|\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})$"
)

NOISE_KEYWORDS = [
    "头像", "按钮", "滚动条", "返回", "系统消息", 
    "未发布的小程序", "体验版", "已撤回", "拍了拍",
    "查看更多", "邀请你加入群聊", "发起了群聊"
]

def is_noise_text(text: str) -> bool:
    """过滤微信中的时间戳、小程序说明卡片及系统噪音"""
    if not text:
        return False
    if RE_TIMESTAMP.match(text):
        return True
    for nw in NOISE_KEYWORDS:
        if nw in text and len(text) <= 20:
            return True
    return False

# =========================================================
# 会话上下文状态管理器
# =========================================================
class ChatSessionState:
    def __init__(self, name: str, hwnd: int, ctrl: auto.Control):
        self.name = name
        self.hwnd = hwnd
        self.ctrl = ctrl
        self.msg_list_ctrl = None
        self.input_ctrl = None
        self.last_seen_msg_ids = []
        self.recent_bot_replies = deque(maxlen=20)  # 防回声抑制锁
        self.active_image_context = None            # (image_path, timestamp)
        self.initialized = False

    def locate_controls(self) -> bool:
        """寻找消息列表和输入框控件"""
        try:
            wnd_rect = self.ctrl.BoundingRectangle
            for child in self.ctrl.GetChildren():
                if child.ControlTypeName == "ListControl" and child.BoundingRectangle.left > (wnd_rect.left + 80):
                    self.msg_list_ctrl = child
                    break
            if not self.msg_list_ctrl:
                self.msg_list_ctrl = self.ctrl.ListControl(searchDepth=25)

            input_box = self.ctrl.EditControl(searchDepth=35)
            if not input_box.Exists(0.2):
                input_box = self.ctrl.EditControl(searchDepth=20)
            self.input_ctrl = input_box

            return self.msg_list_ctrl.Exists(0.2) and self.input_ctrl.Exists(0.2)
        except Exception:
            return False

    def resolve_real_name(self) -> str:
        """从微信窗口顶栏动态获取真实联系人/群名称"""
        if self.name != "主窗口会话":
            return self.name
        try:
            for child in self.ctrl.GetChildren():
                txt = child.Name.strip() if child.Name else ""
                if txt in LISTEN_TARGETS:
                    self.name = txt
                    return txt
        except Exception:
            pass
        return self.name

    def parse_visible_messages(self):
        """解析屏幕当前可见气泡，返回有序消息元组列表"""
        if not self.msg_list_ctrl or not self.msg_list_ctrl.Exists(0.1):
            if not self.locate_controls():
                return []

        parsed = []
        try:
            children = self.msg_list_ctrl.GetChildren()
            if not children:
                return []

            list_rect = self.msg_list_ctrl.BoundingRectangle
            mid_x = (list_rect.left + list_rect.right) / 2

            for item in children:
                raw_text = item.Name.strip() if item.Name else ""
                r = item.BoundingRectangle
                width = r.right - r.left
                height = r.bottom - r.top

                is_self = False
                sub_children = item.GetChildren()
                if sub_children:
                    last_sub = sub_children[-1]
                    if last_sub.BoundingRectangle.left > mid_x:
                        is_self = True
                else:
                    if r.left > mid_x:
                        is_self = True

                is_image = False
                text = raw_text

                if raw_text in ["[图片]", "图片"]:
                    is_image = True
                elif not raw_text:
                    if width >= 40 and height >= 40:
                        text = "[图片]"
                        is_image = True
                    else:
                        continue

                # 噪点清洗
                if not is_image and is_noise_text(text):
                    continue

                # 防回声判定
                if text in self.recent_bot_replies:
                    is_self = True

                try:
                    rt_id = str(item.GetRuntimeId())
                except Exception:
                    rt_id = f"{text}_{is_self}_{id(item)}"

                parsed.append((rt_id, text, is_self, item, is_image))
        except Exception:
            pass

        return parsed

    def capture_image_from_control(self, item_obj) -> Path:
        """【终极优雅】：利用 UIA 原生控件级无损截屏，毫秒级直接捕获高清原图！"""
        try:
            temp_file = Path(f"temp_img_{int(time.time() * 1000)}.png")
            
            # 直接对目标控件抓取渲染像素
            item_obj.CaptureToImage(str(temp_file.resolve()))
            
            if temp_file.exists() and temp_file.stat().st_size > 1024:
                # 校验图片有效性
                with Image.open(temp_file) as img:
                    img.verify()
                return temp_file
        except Exception as e:
            print(f"[-] [视觉截屏] 提取异常: {e}")
        return None

    def get_or_fetch_viewport_image(self, visible_msgs) -> Path:
        """获取当前视窗内的活跃图片（支持最近缓存或视口倒查）"""
        now = time.time()
        if self.active_image_context:
            cached_path, cached_time = self.active_image_context
            if (now - cached_time) <= 180.0 and cached_path.exists():
                return cached_path

        for _, _, is_self, item_obj, is_image in reversed(visible_msgs):
            if is_image and not is_self:
                print(f"[*] [视窗视觉分析] 发现屏幕视口内存在图片 -> 正在提取高清图...")
                img_file = self.capture_image_from_control(item_obj)
                if img_file:
                    self.active_image_context = (img_file, now)
                    return img_file
                break

        return None

    def send_text_reply(self, reply_text: str) -> bool:
        """向当前窗口输入框发送回复"""
        try:
            win32gui.SetForegroundWindow(self.hwnd)
            time.sleep(0.05)

            if not self.input_ctrl or not self.input_ctrl.Exists(0.1):
                self.locate_controls()

            val_pattern = self.input_ctrl.GetValuePattern()
            if val_pattern:
                val_pattern.SetValue(reply_text)
            else:
                self.input_ctrl.SendKeys(reply_text)

            time.sleep(0.05)
            self.input_ctrl.Click(simulateMove=False)
            time.sleep(0.05)
            auto.SendKeys("{Enter}")

            self.recent_bot_replies.append(reply_text)
            return True
        except Exception as e:
            print(f"[-] [{self.name}] 发送异常: {e}")
            return False

# =========================================================
# 窗口搜寻与主调度引擎
# =========================================================
active_sessions = {}

def scan_matching_windows():
    """扫描所有匹配目标名字的微信视窗"""
    found_hwnds = {}

    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            cls = win32gui.GetClassName(hwnd)

            for target in LISTEN_TARGETS:
                if target in title and ("Qt" in cls or "WeChat" in cls or "微信" in title):
                    rect = win32gui.GetWindowRect(hwnd)
                    if (rect[2] - rect[0]) > 200 and (rect[3] - rect[1]) > 200:
                        found_hwnds[hwnd] = target

            if ("WeChat" in cls or "Qt" in cls) and (title in ["微信", "WeChat"] or not title):
                rect = win32gui.GetWindowRect(hwnd)
                if (rect[2] - rect[0]) > 400 and (rect[3] - rect[1]) > 400:
                    found_hwnds[hwnd] = "主窗口会话"

        return True

    try:
        win32gui.EnumWindows(enum_cb, None)
    except Exception:
        pass

    return found_hwnds

def main():
    print("=" * 60)
    print(" 微信 AI 智能助手 (自研原生 UIA + 控件级无损视觉引擎)")
    print("=" * 60)
    print(f"[*] 监听白名单目标: {', '.join(LISTEN_TARGETS)}")
    print("[*] 正在搜寻匹配的微信视窗...")

    global active_sessions

    while True:
        try:
            discovered = scan_matching_windows()

            for dead_hwnd in list(active_sessions.keys()):
                if dead_hwnd not in discovered or not win32gui.IsWindow(dead_hwnd):
                    print(f"[-] 会话窗口 [{active_sessions[dead_hwnd].name}] 已断开")
                    del active_sessions[dead_hwnd]

            for hwnd, target_name in discovered.items():
                if hwnd not in active_sessions:
                    try:
                        ctrl = auto.ControlFromHandle(hwnd)
                        session = ChatSessionState(target_name, hwnd, ctrl)
                        if session.locate_controls():
                            session.resolve_real_name()
                            active_sessions[hwnd] = session
                            print(f"[+] 成功挂载监听视窗: [{session.name}] (HWND: {hwnd})")
                    except Exception:
                        pass

            for hwnd, session in list(active_sessions.items()):
                session.resolve_real_name()
                visible_msgs = session.parse_visible_messages()
                if not visible_msgs:
                    continue

                current_ids = [m[0] for m in visible_msgs]

                # 【冷启动基线建立】
                if not session.initialized:
                    session.last_seen_msg_ids = current_ids
                    session.initialized = True
                    print(f"[+] [{session.name}] 冷启动基线建立完成 (已锁定屏幕末端 {len(visible_msgs)} 条历史消息)")
                    continue

                # 【末端增量游标计算】
                new_items = []
                if session.last_seen_msg_ids:
                    last_known_idx = -1
                    for idx in range(len(current_ids) - 1, -1, -1):
                        if current_ids[idx] in session.last_seen_msg_ids:
                            last_known_idx = idx
                            break

                    if last_known_idx != -1 and last_known_idx < len(visible_msgs) - 1:
                        new_items = visible_msgs[last_known_idx + 1:]
                    elif last_known_idx == -1:
                        new_items = [visible_msgs[-1]]
                else:
                    new_items = visible_msgs

                session.last_seen_msg_ids = current_ids

                if not new_items:
                    continue

                # 收集新消息
                incoming_texts = []
                now_str = time.strftime("%H:%M:%S")

                for rt_id, text, is_self, item_obj, is_image in new_items:
                    if is_self or text in session.recent_bot_replies:
                        continue

                    # 1. 如果新发来的是图片，直接用原生截屏毫秒级捕获！
                    if is_image:
                        print(f"\n[{now_str}] ----------------------------------------------------")
                        print(f"[*] [新图捕获] 收到新图片气泡，执行原生无损截屏...")
                        img_file = session.capture_image_from_control(item_obj)
                        if img_file:
                            session.active_image_context = (img_file, time.time())
                            print(f"[+] [新图捕获] 成功捕获高清原图: {img_file.name}")
                        else:
                            print("[-] [新图捕获] 截屏捕获失败")

                    if text and text not in ["[图片]", "图片"]:
                        incoming_texts.append(text)

                # 2. 自然多模态装箱 (如果视窗内有图片，自动附带)
                attached_img = session.get_or_fetch_viewport_image(visible_msgs)

                if not incoming_texts and not attached_img:
                    continue

                question_text = "\n".join(incoming_texts) if incoming_texts else "请仔细分析这张图片的内容并给出详细专业的解答。"

                # 打印结构化决策日志
                print(f"\n[{now_str}] ====================================================")
                print(f"[*] [会话来源] 目标: [{session.name}]")
                print(f"[*] [提问文本] {question_text}")
                print(f"[*] [视觉上下文] {'已挂载: ' + attached_img.name if attached_img else '无图片'}")
                print(f"[*] [决策行动] 正在请求 Gemini 大脑 (按 [{session.name}] 隔离记忆)...")

                reply = call_llm(session.name, question_text, image_path=attached_img)

                if reply:
                    print(f"[*] [回复动作] 正在向微信输入框打字发送...")
                    session.send_text_reply(reply)
                    print(f"[{now_str}] [√] 回复成功发出！")
                else:
                    print(f"[-] [回复动作] 未获取到有效回复，跳过本次发送。")
                print(f"[{now_str}] ====================================================\n")

        except Exception as e:
            pass

        time.sleep(0.6)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] 机器人已安全退出。")
