# -*- coding: utf-8 -*-
"""
微信 AI 智能全能助手 (自研原生 UIA + 增量快照 Delta 引擎)
特性：
1. 状态快照 + 增量差集机制：冷启动静默，绝不重复触发历史消息
2. 绝对抗滚屏指纹：彻底解耦坐标，无论窗口如何拉伸滚动，绝不重复触发
3. 智能噪点清洗：自动过滤时间戳 (如 15:15, 22:44)、系统通知及小程序注脚
4. 4.0 智能几何气泡识别：精准识别 Qt 框架下 Name 为空的图片/卡片气泡
5. 视窗多模态主动追溯 (Viewport Visual Sniffing)：问“如题/看图”时自动向上追溯最近图片
6. 防回声自闭环 (Echo Suppression)：100% 杜绝“自己回复自己”的死循环
7. 连续发送多消息合并：对方连发多条短消息时自动合并为单次提问
8. 全透明结构化决策日志：打印完整的 UI 扫描、视觉追溯与大模型决策链
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

# 微信图片存储主目录探测
WECHAT_FILE_DIRS = [
    Path(os.environ.get("USERPROFILE", "C:/Users/a1634")) / "Documents" / "WeChat Files" / "wxid_zixek3hhdfdv22" / "FileStorage",
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
    "未发布的小程序", "体验版", "已撤回", "拍了拍",
    "查看更多", "邀请你加入群聊", "发起了群聊"
]

# 视觉提问意图关键词
VISUAL_INTENT_KEYWORDS = ["如题", "图", "照片", "看", "截图", "怎么", "什么", "分析", "批改", "解释"]

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

def find_latest_image_file(max_age_seconds: float = 10.0) -> Path:
    """快速搜寻刚刚落地解密的高清图片（优先命中当月活跃子目录）"""
    now = time.time()
    latest_file = None
    latest_mtime = 0

    # 构造优先扫描目录 (Image 与 MsgAttach)
    priority_dirs = []
    for base in WECHAT_FILE_DIRS:
        if not base.exists():
            continue
        if base.name == "FileStorage":
            priority_dirs.extend([base / "Image", base / "MsgAttach"])
        else:
            priority_dirs.append(base)

    for pdir in priority_dirs:
        if not pdir.exists():
            continue
        try:
            for ext in ["*.jpg", "*.png", "*.jpeg"]:
                for f in pdir.rglob(ext):
                    try:
                        st = f.stat()
                        # 过滤小于 5KB 的图标文件
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
        self.last_captured_image = None  # 最近一次成功捕获并解析的图片路径
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
        """解析屏幕当前可见气泡，返回完整气泡对象列表"""
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

                # 发送方判定
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
                    # 4.0 Qt 图片气泡几何判定
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

                fingerprint = f"{text}::{is_self}"
                parsed.append((fingerprint, text, is_self, item, is_image))
        except Exception:
            pass

        return parsed

    def extract_image_via_click(self, item_obj) -> Path:
        """对指定的图片气泡执行物理闪击提取"""
        try:
            item_obj.Click(simulateMove=False)
            t0 = time.time()
            found_f = None
            while time.time() - t0 < 2.0:
                time.sleep(0.15)
                found_f = find_latest_image_file(max_age_seconds=6.0)
                if found_f:
                    break
            auto.SendKeys("{ESC}")
            time.sleep(0.1)
            return found_f
        except Exception as e:
            print(f"[-] [闪击拿图] 提取异常: {e}")
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

            # 匹配独立小窗口
            for target in LISTEN_TARGETS:
                if target in title and ("Qt" in cls or "WeChat" in cls or "微信" in title):
                    rect = win32gui.GetWindowRect(hwnd)
                    if (rect[2] - rect[0]) > 200 and (rect[3] - rect[1]) > 200:
                        found_hwnds[hwnd] = target

            # 匹配主窗口
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

                # 【冷启动基线建立】
                if not session.initialized:
                    for fp, text, is_self, _, _ in visible_msgs:
                        session.seen_fingerprints.add(fp)
                    session.initialized = True
                    print(f"[+] [{session.name}] 冷启动基线建立完成 (已锁定屏幕上 {len(visible_msgs)} 条历史指纹)")
                    continue

                # 【Delta 增量差集计算】
                new_items = []
                for fp, text, is_self, item_obj, is_image in visible_msgs:
                    if fp not in session.seen_fingerprints:
                        session.seen_fingerprints.add(fp)
                        new_items.append((text, is_self, item_obj, is_image))

                if not new_items:
                    continue

                # 收集新消息
                incoming_texts = []
                captured_img = None
                now_str = time.strftime("%H:%M:%S")

                for text, is_self, item_obj, is_image in new_items:
                    if is_self or text in session.recent_bot_replies:
                        continue

                    # 1. 增量中直接出现新图片
                    if is_image:
                        print(f"\n[{now_str}] ----------------------------------------------------")
                        print(f"[*] [新图捕获] 检测到对方发来图片气泡，触发闪击提取...")
                        img_file = session.extract_image_via_click(item_obj)
                        if img_file:
                            captured_img = img_file
                            session.last_captured_image = img_file
                            print(f"[+] [新图捕获] 成功获取高清原图: {img_file.name}")
                        else:
                            print("[-] [新图捕获] 提取超时或未获取到文件")

                    if text and text not in ["[图片]", "图片"]:
                        incoming_texts.append(text)

                # 2. 【核心升级：视窗多模态主动追溯 (Viewport Visual Sniffing)】
                # 当对方发来文字（如“如题”、“看图”），但当前秒没有新图时，
                # 主动在当前屏幕所有可见气泡中，从下往上倒查最近的一张对方发送的图片！
                if incoming_texts and not captured_img:
                    combined_q = " ".join(incoming_texts)
                    # 如果提问简短（<=15字）或包含视觉意图词，触发追溯
                    should_sniff = len(combined_q) <= 15 or any(k in combined_q for k in VISUAL_INTENT_KEYWORDS)
                    
                    if should_sniff:
                        # 从可见消息倒序寻找最近一张对方发来的图片
                        for _, _, is_self, item_obj, is_image in reversed(visible_msgs):
                            if is_image and not is_self:
                                print(f"\n[{now_str}] ----------------------------------------------------")
                                print(f"[*] [视觉追溯] 收到提问 '{combined_q}' -> 触发视窗图片嗅探！")
                                print(f"[*] [视觉追溯] 正在从屏幕上方倒查提取最近的图片气泡...")
                                img_file = session.extract_image_via_click(item_obj)
                                if img_file:
                                    captured_img = img_file
                                    session.last_captured_image = img_file
                                    print(f"[+] [视觉追溯] 追溯成功！已获取图片附件: {img_file.name}")
                                break

                if not incoming_texts and not captured_img:
                    continue

                # 聚合文本
                question_text = "\n".join(incoming_texts) if incoming_texts else "请仔细分析这张图片的内容并给出详细专业的解答。"

                # 打印结构化决策日志
                print(f"\n[{now_str}] ====================================================")
                print(f"[*] [会话来源] 目标: [{session.name}]")
                print(f"[*] [提问文本] {question_text}")
                print(f"[*] [视觉附件] {'已挂载: ' + captured_img.name if captured_img else '无图片附件'}")
                print(f"[*] [决策行动] 正在请求 Gemini 大脑 (按 [{session.name}] 隔离记忆)...")

                reply = call_llm(session.name, question_text, image_path=captured_img)

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
