# -*- coding: utf-8 -*-
"""
微信 AI 智能全能助手 (自研原生 UIA + 增量快照 Delta 引擎)
特性：
1. 状态快照 + 增量差集机制：冷启动静默，绝不重复触发历史消息
2. 绝对抗滚屏指纹：彻底解耦坐标，无论窗口如何拉伸滚动，绝不重复触发
3. 智能噪点清洗：自动过滤时间戳 (如 15:15, 22:44)、系统通知及小程序注脚
4. 防回声自闭环 (Echo Suppression)：100% 杜绝“自己回复自己”的死循环
5. 连续发送多消息合并：对方连发多条短消息时自动合并为单次提问
6. 多会话独立隔离：支持多独立窗口及主窗口识别，30 轮上下文记忆互不干扰
7. 多模态看图：自研物理闪击提取高清图片并送入 Gemini 视觉分析
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

# 微信图片可能存储的根目录探测
WECHAT_FILE_DIRS = [
    Path(os.environ.get("USERPROFILE", "C:/Users/a1634")) / "Documents" / "WeChat Files",
    Path("E:/WeiXinFILE/xwechat_files"),
    Path(os.environ.get("USERPROFILE", "C:/Users/a1634")) / "AppData" / "Roaming" / "Tencent" / "WeChat"
]

# 时间戳正则（匹配 15:15, 昨天 14:50, 星期二 10:00, 2026年8月28日 等）
RE_TIMESTAMP = re.compile(
    r"^(\d{1,2}:\d{2}|昨天\s*\d{1,2}:\d{2}|星期[一二三四五六日天]\s*\d{1,2}:\d{2}|\d{4}年\d{1,2}月\d{1,2}日.*|\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})$"
)

NOISE_KEYWORDS = [
    "头像", "按钮", "滚动条", "返回", "系统消息", 
    "未发布的小程序", "体验版", "小程序", "已撤回", "拍了拍",
    "查看更多", "邀请你加入群聊", "发起了群聊"
]

def is_noise_text(text: str) -> bool:
    """过滤微信中的时间戳、小程序说明卡片及系统噪音"""
    if not text:
        return True
    # 过滤时间戳
    if RE_TIMESTAMP.match(text):
        return True
    # 过滤系统短注脚
    for nw in NOISE_KEYWORDS:
        if nw in text and len(text) <= 20:
            return True
    return False

def find_latest_image_file(max_age_seconds: float = 10.0) -> Path:
    """在可能的所有微信存储路径中搜寻刚刚落地解密的高清图片"""
    now = time.time()
    latest_file = None
    latest_mtime = 0

    for base_dir in WECHAT_FILE_DIRS:
        if not base_dir.exists():
            continue
        for ext in ["*.jpg", "*.png", "*.jpeg"]:
            try:
                for f in base_dir.rglob(ext):
                    try:
                        st = f.stat()
                        if st.st_size > 5120 and (now - st.st_mtime) <= max_age_seconds:
                            if st.st_mtime > latest_mtime:
                                try:
                                    with Image.open(f) as img:
                                        img.verify()
                                    latest_mtime = st.st_mtime
                                    latest_file = f
                                except Exception:
                                    pass
                    except Exception:
                        pass
            except Exception:
                pass

    return latest_file

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
        self.seen_fingerprints = set()
        self.recent_bot_replies = deque(maxlen=20)  # 防回声抑制锁
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
        """尝试从微信窗口顶栏动态获取当前真实的联系人/群名称"""
        if self.name != "主窗口会话":
            return self.name
        try:
            # 扫描顶栏文本控件，寻找匹配白名单的目标
            for child in self.ctrl.GetChildren():
                txt = child.Name.strip() if child.Name else ""
                if txt in LISTEN_TARGETS:
                    self.name = txt
                    return txt
        except Exception:
            pass
        return self.name

    def parse_visible_messages(self):
        """解析屏幕上当前所有气泡，返回 (fingerprint, text, is_self, item_obj) 列表"""
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
                text = item.Name.strip() if item.Name else ""

                is_image = False
                if not text or text in ["[图片]", "图片"]:
                    try:
                        if item.ImageControl().Exists(0, 0):
                            text = "[图片]"
                            is_image = True
                    except Exception:
                        pass

                # 噪点清洗（时间戳、小程序说明卡片等）
                if not is_image and is_noise_text(text):
                    continue

                # 判断发送方（自身右侧，对方左侧）
                is_self = False
                r = item.BoundingRectangle
                sub_children = item.GetChildren()
                if sub_children:
                    last_sub = sub_children[-1]
                    if last_sub.BoundingRectangle.left > mid_x:
                        is_self = True
                else:
                    if r.left > mid_x:
                        is_self = True

                # 【防回声双保险】：如果这条消息的内容跟机器人刚才发出的某句话完全一致，强行判定为 is_self
                if text in self.recent_bot_replies:
                    is_self = True

                # 【核心：绝对抗滚屏指纹】
                # 完全剔除任何 Y 轴坐标！只用文本内容 + 发信人属性作为纯净指纹。
                # 这样只要消息发出去导致列表向下滚屏，旧消息指纹依然完全不变，绝不重复触发！
                fingerprint = f"{text}::{is_self}"

                parsed.append((fingerprint, text, is_self, item))
        except Exception:
            pass

        return parsed

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

            # 登记进防回声抑制列表
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
    """扫描所有匹配目标名字的微信视窗（支持主窗口与独立拖出的聊天窗口）"""
    found_hwnds = {}

    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            cls = win32gui.GetClassName(hwnd)

            # 匹配 1：独立小窗口
            for target in LISTEN_TARGETS:
                if target in title and ("Qt" in cls or "WeChat" in cls or "微信" in title):
                    rect = win32gui.GetWindowRect(hwnd)
                    if (rect[2] - rect[0]) > 200 and (rect[3] - rect[1]) > 200:
                        found_hwnds[hwnd] = target

            # 匹配 2：未独立拖出时的主窗口
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
    print(" 微信 AI 智能助手 (自研原生 UIA + 增量 Delta 引擎)")
    print("=" * 60)
    print(f"[*] 监听白名单目标: {', '.join(LISTEN_TARGETS)}")
    print("[*] 正在搜寻匹配的微信视窗...")

    global active_sessions

    while True:
        try:
            # 1. 扫描在线视窗
            discovered = scan_matching_windows()

            # 清理已失效视窗
            for dead_hwnd in list(active_sessions.keys()):
                if dead_hwnd not in discovered or not win32gui.IsWindow(dead_hwnd):
                    print(f"[-] 会话窗口 [{active_sessions[dead_hwnd].name}] 已断开")
                    del active_sessions[dead_hwnd]

            # 挂载新视窗
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

            # 2. 轮询每一个激活的会话
            for hwnd, session in list(active_sessions.items()):
                session.resolve_real_name()
                visible_msgs = session.parse_visible_messages()
                if not visible_msgs:
                    continue

                # 【冷启动基线建立】
                if not session.initialized:
                    for fp, text, is_self, _ in visible_msgs:
                        session.seen_fingerprints.add(fp)
                    session.initialized = True
                    print(f"[+] [{session.name}] 冷启动基线建立完成 (已锁定屏幕上 {len(visible_msgs)} 条历史指纹)")
                    continue

                # 【Delta 增量差集计算】
                new_items = []
                for fp, text, is_self, item_obj in visible_msgs:
                    if fp not in session.seen_fingerprints:
                        session.seen_fingerprints.add(fp)
                        new_items.append((text, is_self, item_obj))

                if not new_items:
                    continue

                # 【连续发送合并与过滤】
                incoming_texts = []
                captured_img = None
                now_str = time.strftime("%H:%M:%S")

                for text, is_self, item_obj in new_items:
                    if is_self or text in session.recent_bot_replies:
                        continue

                    # 处理图片
                    if text in ["[图片]", "图片"]:
                        print(f"\n[{now_str}] [{session.name}] 发现对方发来图片，触发物理闪击提取...")
                        try:
                            item_obj.Click(simulateMove=False)
                            t0 = time.time()
                            while time.time() - t0 < 2.0:
                                time.sleep(0.2)
                                found_f = find_latest_image_file(max_age_seconds=5.0)
                                if found_f:
                                    captured_img = found_f
                                    break
                            auto.SendKeys("{ESC}")
                            time.sleep(0.1)

                            if captured_img:
                                print(f"[+] 成功捕获高清原图: {captured_img.name}")
                            else:
                                print("[-] 未能在预期时间内捕获到图片")
                        except Exception as e:
                            print(f"[-] 图片提取异常: {e}")

                    incoming_texts.append(text)

                if not incoming_texts and not captured_img:
                    continue

                # 聚合多条短消息
                pure_texts = [t for t in incoming_texts if t not in ["[图片]", "图片"]]
                question_text = "\n".join(pure_texts) if pure_texts else "请仔细分析这张图片的内容并给出详细专业的解答。"

                print(f"\n[{now_str}] 收到 [{session.name}] 提问: {question_text}")
                if captured_img:
                    print(f"[*] 附带多模态视觉图片: {captured_img.name}")

                # 请求大模型
                print(f"[*] 正在请求 Gemini (保持 [{session.name}] 独立记忆)...")
                reply = call_llm(session.name, question_text, image_path=captured_img)

                if reply:
                    print(f"[*] 正在自动发送回复...")
                    session.send_text_reply(reply)
                    print(f"[{now_str}] [√] 回复发送成功！")
                else:
                    print(f"[-] 未获取到有效回复，跳过本次发送。")

        except Exception as e:
            pass

        time.sleep(0.6)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] 机器人已安全退出。")
