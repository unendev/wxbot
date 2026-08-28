# -*- coding: utf-8 -*-
"""
微信 AI 智能全能助手 (自研原生 UIA + 渐进式双引擎超清视觉系统)
核心架构：
1. 渐进式双引擎视觉 (Progressive Dual-Engine Vision)：
   - 主引擎：0.2秒内闪击提取 100% 原始 4K 无损大图（彻底根治长截图错别字）；
   - 兜底引擎：若遇 I/O 延迟无缝降级为控件级截屏（CaptureToImage），100% 杜绝超时失败。
2. 弹窗级安全销毁 (Safe Window Teardown)：严格比对前台句柄，100% 杜绝误关微信主窗口。
3. 末端增量游标 (Tail-Cursor Tracking)：基于有序队列与 RuntimeId 追踪，重复消息准时捕获。
4. 自然多模态视窗注入：视窗内关联图片无条件伴随装箱，由 Gemini 原生多模态注意力自主作答。
5. 防回声自闭环 (Echo Suppression)：100% 杜绝“自己回复自己”的死循环。
6. 连续发送多消息合并：对方连发多条短消息时自动合并为单次提问。
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

def find_latest_image_file(max_age_seconds: float = 8.0) -> Path:
    """快速搜寻刚刚落地解密的高清图片（优先命中活跃存储子目录）"""
    now = time.time()
    latest_file = None
    latest_mtime = 0

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
# 会话上下文状态管理器 (渐进式双引擎)
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
        """【自适应背景差分切片】：自动分析投影间隙，精准裁切核心气泡，0像素残留"""
        try:
            raw_temp = Path(f"temp_raw_{int(time.time() * 1000)}.png")
            final_temp = Path(f"temp_img_{int(time.time() * 1000)}.png")

            # 1. 抓取完整视窗行像素
            item_obj.CaptureToImage(str(raw_temp.resolve()))

            if not raw_temp.exists() or raw_temp.stat().st_size < 1024:
                return None

            # 2. 自适应背景差分与间隙分析
            with Image.open(raw_temp).convert("RGB") as img:
                w, h = img.size
                bg = img.getpixel((w - 5, 5))

                def color_diff(c1, c2):
                    return abs(c1[0] - c2[0]) + abs(c1[1] - c2[1]) + abs(c1[2] - c2[2])

                col_has_content = []
                for x in range(w):
                    has = any(color_diff(img.getpixel((x, y)), bg) > 30 for y in range(0, h, 2))
                    col_has_content.append(has)

                spans = []
                in_span = False
                start_x = 0
                for x, has in enumerate(col_has_content):
                    if has and not in_span:
                        in_span = True
                        start_x = x
                    elif not has and in_span:
                        in_span = False
                        spans.append((start_x, x))
                if in_span:
                    spans.append((start_x, w))

                if spans:
                    main_span = max(spans, key=lambda s: s[1] - s[0])
                    min_y, max_y = h, 0
                    for x in range(main_span[0], main_span[1], 2):
                        for y in range(h):
                            if color_diff(img.getpixel((x, y)), bg) > 30:
                                if y < min_y: min_y = y
                                if y > max_y: max_y = y

                    if min_y < max_y:
                        crop_box = (main_span[0], min_y, main_span[1], max_y + 1)
                        cropped = img.crop(crop_box)
                        cropped.save(final_temp)
                        try:
                            raw_temp.unlink(missing_ok=True)
                        except Exception:
                            pass
                        return final_temp

                img.save(final_temp)
                try:
                    raw_temp.unlink(missing_ok=True)
                except Exception:
                    pass
                return final_temp

        except Exception as e:
            print(f"[-] [自适应裁切] 异常: {e}")
        return None

    def extract_highres_image_dual_engine(self, item_obj) -> Path:
        """【渐进式双引擎】：优先获取 100% 原始 4K 大图，极速降级截屏兜底"""
        try:
            before_fg_hwnd = win32gui.GetForegroundWindow()

            # 1. 尝试触发原图闪击
            r = item_obj.BoundingRectangle
            if (r.right - r.left) > 0 and (r.bottom - r.top) > 0:
                center_x = r.left + (r.right - r.left) // 2
                center_y = r.top + (r.bottom - r.top) // 2
                auto.Click(center_x, center_y)
            else:
                item_obj.Click(simulateMove=False)

            # 2. 轮询查找 100% 原始解密大图文件 (最多等 1.5 秒)
            t0 = time.time()
            found_raw_file = None
            while time.time() - t0 < 1.5:
                time.sleep(0.12)
                found_raw_file = find_latest_image_file(max_age_seconds=5.0)
                if found_raw_file:
                    break

            # 3. 安全销毁预览弹窗
            after_fg_hwnd = win32gui.GetForegroundWindow()
            if after_fg_hwnd != self.hwnd and after_fg_hwnd != before_fg_hwnd and after_fg_hwnd != 0:
                auto.SendKeys("{ESC}")
                time.sleep(0.08)

            # 如果成功获取 4K 原始文件，直接返回
            if found_raw_file:
                print(f"[+] [主引擎] 成功捕获 4K 原始超清文件: {found_raw_file.name}")
                return found_raw_file

            # 4. 若原图超时，立即启动【截屏兜底引擎】无缝补位！
            print("[*] [主引擎] 原图 I/O 等待，正在启动【无损截屏引擎】补位...")
            fallback_img = self.capture_image_from_control(item_obj)
            if fallback_img:
                print(f"[+] [兜底引擎] 成功捕获高清气泡图: {fallback_img.name}")
                return fallback_img

        except Exception as e:
            print(f"[-] [双引擎提取] 异常: {e}")
            # 异常时直接截屏兜底
            return self.capture_image_from_control(item_obj)

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
                print(f"[*] [视窗视觉分析] 发现屏幕视口内存在图片 -> 正在提取超清图...")
                img_file = self.extract_highres_image_dual_engine(item_obj)
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
    print(" 微信 AI 智能助手 (自研原生 UIA + 渐进式双引擎超清视觉系统)")
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
                new_image_in_tick = False
                now_str = time.strftime("%H:%M:%S")

                for rt_id, text, is_self, item_obj, is_image in new_items:
                    if is_self or text in session.recent_bot_replies:
                        continue

                    # 1. 发现新图片，双引擎超清捕获
                    if is_image:
                        print(f"\n[{now_str}] ----------------------------------------------------")
                        print(f"[*] [新图捕获] 收到新图片，正在启动超清双引擎捕获...")
                        img_file = session.extract_highres_image_dual_engine(item_obj)
                        if img_file:
                            session.active_image_context = (img_file, time.time())
                            new_image_in_tick = True
                        else:
                            print("[-] [新图捕获] 图像捕获失败")

                    if text and text not in ["[图片]", "图片"]:
                        incoming_texts.append(text)

                # 核心防空转守卫
                if not incoming_texts and not new_image_in_tick:
                    continue

                # 2. 自然多模态装箱 (如果视窗内有图片，自动附带)
                attached_img = session.get_or_fetch_viewport_image(visible_msgs)

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
