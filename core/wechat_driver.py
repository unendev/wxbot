# -*- coding: utf-8 -*-
"""
微信 4.0 (Qt 5.15.14) 纯后台静默 UIAutomation 驱动器
严格遵守 STANDARDS.md：
1. 绝不移动物理鼠标光标
2. 绝不强制夺取系统前台焦点
3. 采用 ValuePattern 内存注入与无感静默操作
"""
import ctypes
import logging
import re
import time
from typing import List, Optional, Tuple, Dict
import win32gui
import win32con
import uiautomation as auto
from core.config import config

logger = logging.getLogger("wxbot.driver")

# Windows SPI 无障碍唤醒常量
SPI_SETSCREENREADER = 0x0047
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

# 常见系统时间与界面静态 UI 控件黑名单
TIME_PATTERNS = [
    r"^\d{1,2}:\d{2}$",
    r"^(昨天|前天|星期[一二三四五六日])\s*\d{1,2}:\d{2}$",
    r"^\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2}$",
    r"^\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2}$",
]

# 微信界面占位符与非聊天内容黑名单
UI_NOISE_NAMES = {
    "图片", "头像", "按钮", "查看更多", "未命名", "输入", "发送", "发送(s)", "发送(S)",
    "表情", "发送文件", "截图", "聊天记录", "语音通话", "视频通话", "聊天信息"
}

def is_noise_or_timestamp(text: str) -> bool:
    """过滤微信自动插入的界面时间标签、头像占位与无意义 UI 元素"""
    clean = text.strip()
    if not clean:
        return True
    if clean.lower() in UI_NOISE_NAMES:
        return True
    for pat in TIME_PATTERNS:
        if re.match(pat, clean):
            return True
    return False

class WeChatDriver:
    def __init__(self, cfg=config):
        self.cfg = cfg
        self.main_hwnd = None
        self.main_ctrl = None
        self._ensure_accessibility_enabled()

    def _ensure_accessibility_enabled(self):
        """广播 SPI 无障碍标志，激活微信 Qt 内部隐藏的 UIA 树"""
        try:
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETSCREENREADER, 1, 0, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
            )
        except Exception as e:
            logger.debug(f"广播 SPI 无障碍标志提示: {e}")

    def find_wechat_window(self) -> bool:
        """寻找微信 4.0 (Qt) 主窗口控件 (自适应多屏/副屏坐标)"""
        # 1. 优先使用 UIAutomation 直接按类名查找
        try:
            for cls in ["Qt51514QWindowIcon", "WeChatMainWndForPC"]:
                win = auto.WindowControl(searchDepth=1, ClassName=cls)
                if win.Exists(0.1):
                    self.main_ctrl = win
                    self.main_hwnd = win.NativeWindowHandle
                    return True
        except Exception as e:
            logger.debug(f"UIA 直接查找提示: {e}")

        # 2. 遍历桌面顶级控件 (模糊匹配微信标题或类名)
        try:
            root = auto.GetRootControl()
            for child in root.GetChildren():
                c_name = child.Name or ""
                c_cls = child.ClassName or ""
                if "微信" in c_name or c_cls in ["Qt51514QWindowIcon", "WeChatMainWndForPC"]:
                    self.main_ctrl = child
                    self.main_hwnd = child.NativeWindowHandle
                    return True
        except Exception as e:
            logger.debug(f"UIA 遍历查找提示: {e}")

        # 3. 备用通过 FindWindow 快速查找
        try:
            for cls in ["Qt51514QWindowIcon", "WeChatMainWndForPC"]:
                hwnd = win32gui.FindWindow(cls, None)
                if hwnd and win32gui.IsWindow(hwnd):
                    self.main_hwnd = hwnd
                    self.main_ctrl = auto.ControlFromHandle(hwnd)
                    return True
        except Exception as e:
            logger.debug(f"FindWindow 查找提示: {e}")

        self.main_hwnd = None
        self.main_ctrl = None
        return False

    def get_current_chat_title(self) -> Optional[str]:
        """获取当前正在打开的群聊/私聊标题"""
        if not self.main_ctrl:
            return None
        try:
            title_ctrl = self.main_ctrl.TextControl(searchDepth=15)
            if title_ctrl.Exists(0.2):
                return title_ctrl.Name
        except Exception:
            pass
        return None

    def read_visible_messages(self) -> List[Dict[str, str]]:
        """
        静默读取当前聊天窗口中的真实聊天消息列表
        返回格式: [{"id": str, "type": "text"|"image", "content": str}]
        """
        if not self.main_ctrl:
            return []

        try:
            msg_list = self.main_ctrl.ListControl(searchDepth=35, Name="消息")
            if not msg_list.Exists(0.5):
                msg_list = self.main_ctrl.ListControl(searchDepth=25)
                if not msg_list.Exists(0.5):
                    return []

            children = msg_list.GetChildren()
            results = []
            for item in children:
                name = item.Name
                if not name:
                    continue

                clean_text = name.strip()
                if is_noise_or_timestamp(clean_text):
                    continue

                rect = item.BoundingRectangle
                item_id = f"{clean_text}_{rect.left}_{rect.top}"

                msg_type = "text"
                if clean_text == "[图片]":
                    msg_type = "image"

                results.append({
                    "id": item_id,
                    "type": msg_type,
                    "content": clean_text,
                    "control": item,
                })

            return results
        except Exception as e:
            logger.error(f"[Driver] 读取消息流异常: {e}")
            return []

    def send_text_silent(self, text: str) -> bool:
        """
        纯后台静默发送文本（无物理鼠标移动、无前台激活抢占）
        1. 利用 ValuePattern 直接写入输入框
        2. 触发发送按钮或软回车进行发出
        """
        if not self.main_ctrl or not text:
            return False

        try:
            input_box = self.main_ctrl.EditControl(searchDepth=30, Name="输入")
            if not input_box.Exists(0.8):
                input_box = self.main_ctrl.EditControl(searchDepth=25)
                if not input_box.Exists(0.5):
                    logger.warning("[Driver] 未定位到微信输入框")
                    return False

            # 1. 内存直接注入内容
            val_pattern = input_box.GetValuePattern()
            if val_pattern:
                val_pattern.SetValue(text)
            else:
                input_box.SendKeys(text)

            time.sleep(0.15)

            # 2. 寻找发送按钮并触发
            sent = False
            for btn_name in ["发送(S)", "发送", "发送(s)", "Send"]:
                send_btn = self.main_ctrl.ButtonControl(searchDepth=30, Name=btn_name)
                if send_btn.Exists(0.1):
                    # 优先 InvokePattern
                    inv = send_btn.GetInvokePattern()
                    if inv:
                        inv.Invoke()
                        sent = True
                        break
                    else:
                        # 软点击（不移动物理鼠标）
                        send_btn.Click(simulateMove=False)
                        sent = True
                        break

            # 3. 兜底回车触发
            if not sent:
                # 软聚焦输入框并回车
                try:
                    input_box.SetFocus()
                except Exception:
                    pass
                input_box.SendKeys("{Enter}")

            logger.info(f"[Driver] 成功静默发送回复: {text[:20]}...")
            return True
        except Exception as e:
            logger.error(f"[Driver] 静默发送异常: {e}")
            return False
