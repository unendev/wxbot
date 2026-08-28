# -*- coding: utf-8 -*-
"""
微信 4.0 极简稳定驱动 (基于 10a8371 黄金实测可用版本)
"""
import ctypes
import logging
import re
import time
from typing import List, Optional
import uiautomation as auto
import win32con
import win32gui

from core.config import config
from core.domain import ChatMessage

logger = logging.getLogger("wxbot.driver")

SPI_SETSCREENREADER = 0x0046
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

# 常见系统时间、进度条与系统通知正则黑名单
NOISE_PATTERNS = [
    r"^\d{1,2}:\d{2}$",
    r"^(昨天|前天|星期[一二三四五六日])\s*\d{1,2}:\d{2}$",
    r"^\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2}$",
    r"^\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2}$",
    r"^.*(视频|文件)\s*进度:\s*\d+%.*$",
    r"^(正在发送|发送中|重发)\b.*$",
    r"^(视频|文件)\s*\d{1,2}:\d{2}$",
    r"^.*撤回了一条消息.*$",
    r"^.*拍了拍.*$",
    r"^\[(微信红包|转账|位置|语音通话|视频通话|名片|群待办)\]$",
    r"^通话时长\s*\d{1,2}:\d{2}$",
    r"^对方已(拒绝|挂断|取消).*$",
    r"^.*已添加好友，现在可以开始聊天了.*$",
]

UI_NOISE_NAMES = {
    "图片", "头像", "按钮", "查看更多", "未命名", "输入", "发送", "发送(s)", "发送(S)",
    "表情", "发送文件", "截图", "聊天记录", "语音通话", "视频通话", "聊天信息", "更多",
    "选择", "添加", "搜索", "关闭", "最小化", "最大化", "还原"
}

def is_noise_or_timestamp(text: str) -> bool:
    clean = text.strip()
    if not clean or clean.lower() in UI_NOISE_NAMES:
        return True
    for pat in NOISE_PATTERNS:
        if re.match(pat, clean, re.IGNORECASE):
            return True
    return False

class WeChatDriver:
    def __init__(self, cfg=config):
        self.cfg = cfg
        self.main_hwnd = None
        self.main_ctrl = None
        self._ensure_accessibility_enabled()

    def _ensure_accessibility_enabled(self):
        try:
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETSCREENREADER, 1, 0, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
            )
        except Exception:
            pass

    def find_wechat_window(self) -> bool:
        try:
            for cls in ["Qt51514QWindowIcon", "WeChatMainWndForPC"]:
                win = auto.WindowControl(searchDepth=1, ClassName=cls)
                if win.Exists(0.2):
                    self.main_ctrl = win
                    self.main_hwnd = win.NativeWindowHandle
                    return True
        except Exception:
            pass

        try:
            root = auto.GetRootControl()
            for child in root.GetChildren():
                c_name = child.Name or ""
                c_cls = child.ClassName or ""
                if "微信" in c_name or c_cls in ["Qt51514QWindowIcon", "WeChatMainWndForPC"]:
                    self.main_ctrl = child
                    self.main_hwnd = child.NativeWindowHandle
                    return True
        except Exception:
            pass

        return False

    def get_tail_messages(self, limit: int = 5) -> List[ChatMessage]:
        if not self.main_ctrl:
            return []

        try:
            msg_list = self.main_ctrl.ListControl(searchDepth=30, Name="消息")
            if not msg_list.Exists(0.2):
                msg_list = self.main_ctrl.ListControl(searchDepth=20)
                if not msg_list.Exists(0.2):
                    return []

            children = msg_list.GetChildren()
            if not children:
                return []

            tail_items = children[-limit:] if len(children) > limit else children
            results = []

            list_rect = msg_list.BoundingRectangle
            list_mid_x = (list_rect.left + list_rect.right) / 2 if list_rect.right > list_rect.left else None

            for item in tail_items:
                name = item.Name
                if not name:
                    continue

                clean_text = name.strip()
                if is_noise_or_timestamp(clean_text):
                    continue

                # 1. 基础前缀匹配
                sender_type = "user"
                if clean_text.startswith(f"{self.cfg.bot_name}:") or clean_text.startswith(f"{self.cfg.bot_name}："):
                    sender_type = "bot"

                # 2. 气泡水平坐标精准判断 (基于微信右边缘贴合机制)
                item_rect = item.BoundingRectangle
                if list_rect and item_rect.right > 0:
                    is_right_aligned = (
                        item_rect.right >= list_rect.right - 95 or
                        (list_mid_x and item_rect.left > list_mid_x)
                    )
                    if is_right_aligned:
                        sender_type = "bot"

                msg_type = "text"
                if clean_text == "[图片]":
                    msg_type = "image"

                msg = ChatMessage(
                    content=clean_text,
                    sender_type=sender_type,
                    msg_type=msg_type
                )
                results.append(msg)

            return results
        except Exception as e:
            logger.error(f"[Driver] 提取消息流尾部异常: {e}")
            return []

    def send_text_silent(self, text: str) -> bool:
        if not self.main_ctrl or not text:
            return False

        try:
            # 尝试激活前台确保 100% 成功
            try:
                if self.main_hwnd:
                    win32gui.SetForegroundWindow(self.main_hwnd)
                    time.sleep(0.05)
            except Exception:
                pass

            input_box = self.main_ctrl.EditControl(searchDepth=30, Name="输入")
            if not input_box.Exists(0.5):
                input_box = self.main_ctrl.EditControl(searchDepth=25)
                if not input_box.Exists(0.3):
                    logger.warning("[Driver] 未定位到微信输入框")
                    return False

            # 1. 内存写入
            val_pattern = input_box.GetValuePattern()
            if val_pattern:
                val_pattern.SetValue(text)
            else:
                input_box.SendKeys(text)

            time.sleep(0.05)

            # 2. 回车投递
            target_hwnd = input_box.NativeWindowHandle or self.main_hwnd
            if target_hwnd and win32gui.IsWindow(target_hwnd):
                win32gui.PostMessage(target_hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
                time.sleep(0.05)
                win32gui.PostMessage(target_hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)

            # 3. 发送按钮联合触发
            for btn_name in ["发送(S)", "发送", "发送(s)", "Send"]:
                send_btn = self.main_ctrl.ButtonControl(searchDepth=20, Name=btn_name)
                if send_btn.Exists(0.1):
                    inv = send_btn.GetInvokePattern()
                    if inv:
                        inv.Invoke()
                    else:
                        send_btn.Click(simulateMove=False)
                    break

            logger.info(f"[Driver] 成功发送回复: {text[:25]}...")
            return True
        except Exception as e:
            logger.error(f"[Driver] 发送异常: {e}")
            return False
