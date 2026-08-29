# -*- coding: utf-8 -*-
"""
微信 AI 智能全能助手
架构特性：
1. 工业级标准 Logging 输出规范 (时间戳 + LogLevel + 模块定位 + 结构化信息)
2. 拟人化群聊协同引擎 (私聊免@自由对话，群聊静默维持热缓存+@点名唤醒)
3. 渐进式双引擎超清视觉 (0.2s 原始 4K 文件闪击 + 自适应背景差分无损切片兜底)
4. 弹窗级安全销毁 (Safe Window Teardown 防误关主窗口)
5. 末端增量游标 (Tail-Cursor Tracking 防失聪与重复消息)
6. 防回声自闭环 (Echo Suppression 杜绝死循环)
"""
import os
import re
import sys
import time
import json
import queue
import ctypes
import logging
import threading
from pathlib import Path
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from PIL import Image

# 1. 控制台编码与标准 Logging 初始化
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("wxbot")

import win32gui
import uiautomation as auto
from llm_service import call_llm

# =========================================================
# 配置区：监听目标与群聊识别
# =========================================================
# 个人私聊目标：自动自由上下文对话
# 群聊目标：静默维护上下文与图片缓存，必须 @ 机器人才会触发作答
GROUP_TARGETS = ["小丑", "大丑", "小丑之家", "大丑之家", "大白鲨、轩轩、bot"]
PRIVATE_TARGETS = ["bot", "渥奇", "活出自己"]

LISTEN_TARGETS = PRIVATE_TARGETS + GROUP_TARGETS

# 视觉目标全量标记集合 (覆盖普通图片、高清原图、大表情包、自定义动图表情、英文Sticker等)
IMAGE_MARKERS = {
    "[图片]", "图片", "[Image]", "Image",
    "[动画表情]", "动画表情", "[表情]", "表情",
    "[Sticker]", "Sticker", "[Emoji]", "Emoji"
}

# 禁用 Windows 控制台快速编辑模式 (彻底防止鼠标误触点击黑框导致 Python 进程被 Windows 强制挂起暂停)
try:
    kernel32 = ctypes.windll.kernel32
    h_stdin = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
    mode = ctypes.c_uint32()
    if kernel32.GetConsoleMode(h_stdin, ctypes.byref(mode)):
        ENABLE_QUICK_EDIT_MODE = 0x0040
        ENABLE_EXTENDED_FLAGS = 0x0080
        new_mode = (mode.value & ~ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS
        kernel32.SetConsoleMode(h_stdin, new_mode)
except Exception:
    pass

# 激活系统屏幕无障碍辅助支持
SPI_SETSCREENREADER = 0x0046
try:
    ctypes.windll.user32.SystemParametersInfoW(SPI_SETSCREENREADER, 1, 0, 1)
except Exception:
    pass

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
    """快速搜寻刚刚落地解密的高清图片"""
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
        self.is_group = name in GROUP_TARGETS
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
        """从微信窗口顶栏动态获取真实联系人/群名称并智能判定群聊属性"""
        # 凡是带有人数后缀 (数字) 或在群聊名单中的，一律铁律锁定为群聊模式 (必须 @ 唤醒)
        if re.search(r"\(\d+\)", self.raw_name) or any(gt in self.raw_name for gt in GROUP_TARGETS):
            self.is_group = True

        if self.name != "主窗口会话":
            return self.name

        try:
            sorted_targets = sorted(LISTEN_TARGETS, key=len, reverse=True)
            for child in self.ctrl.GetChildren():
                txt = child.Name.strip() if child.Name else ""
                for target in sorted_targets:
                    if target in txt:
                        self.name = target
                        self.is_group = re.search(r"\(\d+\)", txt) is not None or any(gt in txt for gt in GROUP_TARGETS)
                        return self.name
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

                is_image = any(m in raw_text for m in IMAGE_MARKERS) or raw_text in IMAGE_MARKERS
                text = raw_text

                if not is_image and not raw_text:
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
            logger.warning("[%s] Failed to perform adaptive image cropping: %s", self.name, e)
        return None

    def extract_highres_image_dual_engine(self, item_obj) -> Path:
        """【渐进式双引擎】：优先获取 100% 原始 4K 大图，极速降级截屏兜底"""
        try:
            before_fg_hwnd = win32gui.GetForegroundWindow()

            r = item_obj.BoundingRectangle
            if (r.right - r.left) > 0 and (r.bottom - r.top) > 0:
                center_x = r.left + (r.right - r.left) // 2
                center_y = r.top + (r.bottom - r.top) // 2
                auto.Click(center_x, center_y)
            else:
                item_obj.Click(simulateMove=False)

            t0 = time.time()
            found_raw_file = None
            while time.time() - t0 < 1.5:
                time.sleep(0.12)
                found_raw_file = find_latest_image_file(max_age_seconds=5.0)
                if found_raw_file:
                    break

            after_fg_hwnd = win32gui.GetForegroundWindow()
            if after_fg_hwnd != self.hwnd and after_fg_hwnd != before_fg_hwnd and after_fg_hwnd != 0:
                auto.SendKeys("{ESC}")
                time.sleep(0.08)

            if found_raw_file:
                logger.info("[%s] Captured raw image file: '%s'", self.name, found_raw_file.name)
                return found_raw_file

            logger.info("[%s] Raw file I/O timed out, falling back to UI capture", self.name)
            fallback_img = self.capture_image_from_control(item_obj)
            if fallback_img:
                logger.info("[%s] Captured UI fallback image: '%s'", self.name, fallback_img.name)
                return fallback_img

        except Exception as e:
            logger.warning("[%s] Error during dual-engine image extraction: %s", self.name, e)
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
                logger.info("[%s] Image detected in viewport, extracting...", self.name)
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
            logger.error("[%s] Failed to send reply text: %s", self.name, e)
            return False

# =========================================================
# 微信主动推送网关 (Universal Push Webhook Gateway)
# =========================================================
PUSH_PORT = int(os.getenv("PUSH_PORT", "5005"))
push_tasks_queue = queue.Queue()

class PushWebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 静默处理常规 HTTP 访问日志，保持终端清爽
        return

    def do_POST(self):
        if self.path in ["/send", "/push"]:
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")
                data = json.loads(body)

                target = data.get("target", "").strip()
                text = data.get("text", "") or data.get("message", "")
                image_path = data.get("image", "")

                if not target or (not text and not image_path):
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "error", "message": "Missing 'target' or 'text' parameter"}, ensure_ascii=False).encode("utf-8"))
                    return

                resp_event = threading.Event()
                result_box = {"status": "pending", "message": ""}
                push_tasks_queue.put((target, text, image_path, resp_event, result_box))

                # 等待主调度引擎执行注入 (最长等待 5 秒)
                resp_event.wait(timeout=5.0)

                status_code = 200 if result_box["status"] == "ok" else 500
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(result_box, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path in ["/status", "/"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            sessions = [s.name for s in active_sessions.values()]
            self.wfile.write(json.dumps({
                "status": "online",
                "service": "WeChat Bot & Push Webhook Gateway",
                "port": PUSH_PORT,
                "active_sessions": sessions
            }, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def start_push_server():
    """在后台常驻启动推送网关 Webhook"""
    try:
        server = HTTPServer(("0.0.0.0", PUSH_PORT), PushWebhookHandler)
        logger.info("[PUSH GATEWAY] HTTP Webhook listening on http://0.0.0.0:%d/send", PUSH_PORT)
        server.serve_forever()
    except Exception as e:
        logger.error("[PUSH GATEWAY] Failed to bind port %d: %s", PUSH_PORT, e)

# =========================================================
# 窗口搜寻与主调度引擎
# =========================================================
active_sessions = {}

def cleanup_temp_files():
    """定期清理历史临时切片图片 (保留最近10分钟)，确保磁盘永久 0 膨胀"""
    now = time.time()
    for p in Path(".").glob("temp_*.png"):
        try:
            if now - p.stat().st_mtime > 600:
                p.unlink(missing_ok=True)
        except Exception:
            pass

def scan_matching_windows():
    """扫描所有匹配目标名字的微信视窗"""
    cleanup_temp_files()
    found_hwnds = {}

    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            cls = win32gui.GetClassName(hwnd)

            # 最长匹配优先：防止 "bot" 误拦截 "大白鲨、轩轩、bot"
            sorted_targets = sorted(LISTEN_TARGETS, key=len, reverse=True)
            for target in sorted_targets:
                if target in title:
                    rect = win32gui.GetWindowRect(hwnd)
                    if (rect[2] - rect[0]) > 200 and (rect[3] - rect[1]) > 200:
                        found_hwnds[hwnd] = target
                        break

            if ("WeChat" in cls or "Qt" in cls or "ChatWnd" in cls) and (title in ["微信", "WeChat"] or not title):
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
    logger.info("Initializing WeChat Bot (Native UIA Engine)")
    logger.info("Monitoring targets: %s (Group targets: %s)", LISTEN_TARGETS, GROUP_TARGETS)

    # 启动通用主动推送 Webhook 接收服务 (后台守护线程)
    threading.Thread(target=start_push_server, daemon=True).start()

    global active_sessions

    while True:
        try:
            discovered = scan_matching_windows()

            for dead_hwnd in list(active_sessions.keys()):
                if dead_hwnd not in discovered or not win32gui.IsWindow(dead_hwnd):
                    logger.warning("Session detached: [%s] (HWND: %d)", active_sessions[dead_hwnd].name, dead_hwnd)
                    del active_sessions[dead_hwnd]

            for hwnd, target_name in discovered.items():
                if hwnd not in active_sessions:
                    try:
                        ctrl = auto.ControlFromHandle(hwnd)
                        session = ChatSessionState(target_name, hwnd, ctrl)
                        if session.locate_controls():
                            session.resolve_real_name()
                            active_sessions[hwnd] = session
                            logger.info(
                                "Attached session: [%s] (HWND: %d, Mode: %s)",
                                session.name, hwnd, "Group" if session.is_group else "Private"
                            )
                    except Exception:
                        pass

            # -------------------------------------------------------------
            # 【主动推送网关任务派发调度】
            # -------------------------------------------------------------
            while not push_tasks_queue.empty():
                try:
                    target_name, push_text, push_img, resp_ev, res_box = push_tasks_queue.get_nowait()
                    matched_session = None
                    for s in active_sessions.values():
                        if target_name in s.name or s.name in target_name:
                            matched_session = s
                            break

                    if matched_session:
                        success = matched_session.send_text_reply(push_text)
                        if success:
                            res_box["status"] = "ok"
                            res_box["message"] = f"Push successfully delivered to [{matched_session.name}]"
                            logger.info("[PUSH GATEWAY] Delivered push message to [%s]: %s", matched_session.name, push_text[:50])
                        else:
                            res_box["status"] = "error"
                            res_box["message"] = f"Failed to send text to window [{matched_session.name}]"
                    else:
                        active_names = [s.name for s in active_sessions.values()]
                        res_box["status"] = "error"
                        res_box["message"] = f"Target [{target_name}] not found in active windows {active_names}"
                        logger.warning("[PUSH GATEWAY] Push target [%s] not found in active windows %s", target_name, active_names)

                    resp_ev.set()
                except queue.Empty:
                    break

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
                    logger.info("[%s] Cold-start baseline established (%d messages synchronized)", session.name, len(visible_msgs))
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
                has_at_mention = False

                for rt_id, text, is_self, item_obj, is_image in new_items:
                    if is_self or text in session.recent_bot_replies:
                        continue

                    # 1. 发现新图片：静默捕获并缓存至视觉热池
                    if is_image:
                        logger.info("[%s] New image received, caching visual context...", session.name)
                        img_file = session.extract_highres_image_dual_engine(item_obj)
                        if img_file:
                            session.active_image_context = (img_file, time.time())
                            new_image_in_tick = True
                            logger.info("[%s] Visual context cached: '%s'", session.name, img_file.name)
                        else:
                            logger.warning("[%s] Failed to capture image", session.name)

                    if text and text not in IMAGE_MARKERS and not any(m == text for m in IMAGE_MARKERS):
                        # 检查是否有 @ 唤醒标记
                        if "@" in text or "@" in item_obj.Name:
                            has_at_mention = True

                        # 剥离开头的 @ 提到前缀 (如 @大丑、@bot)，避免大模型产生误解
                        clean_t = re.sub(r"@\S+[\s\u2005]*", "", text).strip()
                        if not clean_t:
                            clean_t = text.strip()

                        # 群聊模式下：提取发言群友昵称，格式化为 【群友昵称】: 消息内容
                        if session.is_group:
                            sender_name = ""
                            # 从 WeChat 4.0 控件树中提取发送人
                            try:
                                for sub in item_obj.GetChildren():
                                    if sub.ControlTypeName in ["ButtonControl", "TextControl"] and sub.Name and sub.Name != text and sub.Name not in ["[图片]", "Image"]:
                                        sender_name = sub.Name.strip()
                                        break
                            except Exception:
                                pass
                            
                            # 兜底从冒号中提取
                            if not sender_name and (":" in item_obj.Name or "：" in item_obj.Name):
                                parts = re.split(r"[:：]", item_obj.Name, maxsplit=1)
                                if len(parts) == 2 and parts[0].strip():
                                    sender_name = parts[0].strip()

                            if sender_name:
                                incoming_texts.append(f"【{sender_name}】: {clean_t}")
                            else:
                                incoming_texts.append(clean_t)
                        else:
                            incoming_texts.append(clean_t)

                # =====================================================
                # 拟人化触发守卫 (Trigger Guard)
                # =====================================================
                # 1. 基础防空转：无有效文字且无新图
                if not incoming_texts and not new_image_in_tick:
                    continue

                # 2. 群聊静默守卫：若为群聊且无人 @ 机器人 -> 默默维持热缓存，绝不插嘴！
                if session.is_group and not has_at_mention:
                    continue

                # 3. 自然多模态装箱
                attached_img = session.get_or_fetch_viewport_image(visible_msgs)
                question_text = "\n".join(incoming_texts) if incoming_texts else ""

                logger.info(
                    "[%s] Inbound query (Type: %s, Text: '%s', Image: %s)",
                    session.name,
                    "Group-Mention" if session.is_group else "Private",
                    question_text if question_text else "<Pure-Image>",
                    attached_img.name if attached_img else "None"
                )

                reply = call_llm(session.name, question_text, image_path=attached_img)

                if reply:
                    session.send_text_reply(reply)
                    logger.info("[%s] Reply dispatched successfully", session.name)
                else:
                    logger.warning("[%s] Empty LLM response, skipped sending", session.name)

        except Exception as e:
            logger.error("Runtime loop exception: %s", e)

        time.sleep(0.6)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot process exited gracefully.")
