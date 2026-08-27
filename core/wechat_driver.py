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
        """寻找微信 4.0 (Qt) 主窗口句柄 (防卡死快速过滤)"""
        # 1. 优先尝试直接快速匹配常见类名
        target_classes = ["Qt51514QWindowIcon", "WeChatMainWndForPC"]
        for cls in target_classes:
            hwnd = win32gui.FindWindow(cls, "微信")
            if hwnd and win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                self.main_hwnd = hwnd
                self.main_ctrl = auto.ControlFromHandle(self.main_hwnd)
                return True

        # 2. 若直接查找未命中，则枚举顶级窗口 (先类名过滤，避免 GetWindowText 阻塞)
        hwnds = []
        def enum_cb(hwnd, _):
            try:
                if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                    return True
                cls_name = win32gui.GetClassName(hwnd)
                if cls_name in target_classes:
                    title = win32gui.GetWindowText(hwnd)
                    if title == "微信":
                        hwnds.append(hwnd)
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_cb, None)
        except Exception as e:
            logger.debug(f"枚举窗口提示: {e}")

        if not hwnds:
            self.main_hwnd = None
            self.main_ctrl = None
            return False

        self.main_hwnd = hwnds[0]
        self.main_ctrl = auto.ControlFromHandle(self.main_hwnd)
        return True

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
        静默读取当前聊天窗口中的可见消息列表
        返回格式: [{"id": str, "type": "text"|"image", "content": str}]
        """
        if not self.main_ctrl:
            return []

        try:
            # 微信 4.0 消息流通常嵌套在深度 20~35 层的 ListControl(Name="消息")
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
                rect = item.BoundingRectangle
                item_id = f"{clean_text}_{rect.left}_{rect.top}"

                msg_type = "text"
                if "[图片]" in clean_text or "图片" in item.ControlTypeName:
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
        利用 ValuePattern 直接写入输入框
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

            val_pattern = input_box.GetValuePattern()
            if val_pattern:
                val_pattern.SetValue(text)
            else:
                input_box.SendKeys(text)

            time.sleep(0.1)

            send_btn = self.main_ctrl.ButtonControl(searchDepth=30, Name="发送(S)")
            if not send_btn.Exists(0.2):
                send_btn = self.main_ctrl.ButtonControl(searchDepth=30, Name="发送")

            if send_btn.Exists(0.2):
                invoke_pattern = send_btn.GetInvokePattern()
                if invoke_pattern:
                    invoke_pattern.Invoke()
                else:
                    send_btn.Click(simulateMove=False)
            else:
                input_box.SendKeys("{Enter}")

            logger.info(f"[Driver] 成功静默发送回复: {text[:20]}...")
            return True
        except Exception as e:
            logger.error(f"[Driver] 静默发送异常: {e}")
            return False
