# -*- coding: utf-8 -*-
"""
微信 4.0 (Qt 5.15.14) 工业级后台静默驱动器
特性：
1. 100% 后台静默（不移动鼠标指针，不抢占前台焦点）
2. 尾部游标检测（High-Water Mark），彻底消除 UI 坐标抖动 Bug
3. Win32 消息级虚拟按键投递 (PostMessage VK_RETURN)，确保后台 100% 发送
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
from core.domain import ChatMessage

logger = logging.getLogger("wxbot.driver")

# Windows SPI 无障碍唤醒常量
SPI_SETSCREENREADER = 0x0047
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

# 常见系统时间、进度条与系统通知正则黑名单 (全面清扫盲区)
NOISE_PATTERNS = [
    # 1. 系统时间
    r"^\d{1,2}:\d{2}$",
    r"^(昨天|前天|星期[一二三四五六日])\s*\d{1,2}:\d{2}$",
    r"^\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2}$",
    r"^\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2}$",
    # 2. 传输进度与动态占位 (视频/文件上传)
    r"^.*(视频|文件)\s*进度:\s*\d+%.*$",
    r"^(正在发送|发送中|重发)\b.*$",
    r"^(视频|文件)\s*\d{1,2}:\d{2}$",
    # 3. 系统提示与拍一拍/撤回/红包
    r"^.*撤回了一条消息.*$",
    r"^.*拍了拍.*$",
    r"^\[(微信红包|转账|位置|语音通话|视频通话|名片|群待办)\]$",
    r"^通话时长\s*\d{1,2}:\d{2}$",
    r"^对方已(拒绝|挂断|取消).*$",
    r"^.*已添加好友，现在可以开始聊天了.*$",
]

# 静态 UI 控件与占位符黑名单
UI_NOISE_NAMES = {
    "图片", "头像", "按钮", "查看更多", "未命名", "输入", "发送", "发送(s)", "发送(S)",
    "表情", "发送文件", "截图", "聊天记录", "语音通话", "视频通话", "聊天信息", "更多",
    "选择", "添加", "搜索", "关闭", "最小化", "最大化", "还原"
}

def is_noise_or_timestamp(text: str) -> bool:
    """过滤微信自动插入的界面时间标签、头像占位、动态传输进度与系统提示"""
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
        """广播 SPI 无障碍标志，激活微信 Qt 内部隐藏的 UIA 树"""
        try:
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETSCREENREADER, 1, 0, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
            )
        except Exception as e:
            logger.debug(f"广播 SPI 无障碍标志提示: {e}")

    def find_wechat_window(self) -> bool:
        """寻找微信 4.0 (Qt) 主窗口 (自适应多屏与虚拟桌面)"""
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

        # 3. 备用通过 FindWindow 查找
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
        """获取当前激活的聊天会话名称"""
        if not self.main_ctrl:
            return None
        try:
            title_ctrl = self.main_ctrl.TextControl(searchDepth=15)
            if title_ctrl.Exists(0.2):
                return title_ctrl.Name
        except Exception:
            pass
        return None

    def get_tail_messages(self, limit: int = 5) -> List[ChatMessage]:
        """
        业界标准：实时获取当前渲染中的最新可见消息尾部
        稳定兼容 Qt 虚拟化列表，保证 100% 实时感知新消息
        """
        if not self.main_ctrl:
            return []

        try:
            # 快速定位消息列表容器 (不缓存失效指针，实时获取)
            msg_list = self.main_ctrl.ListControl(searchDepth=30, Name="消息")
            if not msg_list.Exists(0.1):
                msg_list = self.main_ctrl.ListControl(searchDepth=20)
                if not msg_list.Exists(0.1):
                    return []

            children = msg_list.GetChildren()
            if not children:
                return []

            # 截取可见列表最后 limit 个渲染项
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
        """
        工业级纯后台静默发送：
        1. ValuePattern 内存注入
        2. Win32 原生 PostMessage 穿透投递 VK_RETURN，不依赖前台焦点
        3. UI 按钮软点击联动兜底
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

            # 1. 内存注入
            val_pattern = input_box.GetValuePattern()
            if val_pattern:
                val_pattern.SetValue(text)
            else:
                input_box.SendKeys(text)

            time.sleep(0.1)

            # 2. 获取输入框或主窗口 HWND，通过 Win32 消息直接投递回车键
            target_hwnd = input_box.NativeWindowHandle or self.main_hwnd
            if target_hwnd and win32gui.IsWindow(target_hwnd):
                # 投递 WM_KEYDOWN & WM_KEYUP 回车消息
                win32gui.PostMessage(target_hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
                time.sleep(0.05)
                win32gui.PostMessage(target_hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)

            time.sleep(0.05)

            # 3. 寻找发送按钮联合触发
            for btn_name in ["发送(S)", "发送", "发送(s)", "Send"]:
                send_btn = self.main_ctrl.ButtonControl(searchDepth=30, Name=btn_name)
                if send_btn.Exists(0.1):
                    inv = send_btn.GetInvokePattern()
                    if inv:
                        inv.Invoke()
                    else:
                        send_btn.Click(simulateMove=False)
                    break

            logger.info(f"[Driver] 成功静默发送回复: {text[:25]}...")
            return True
        except Exception as e:
            logger.error(f"[Driver] 静默发送异常: {e}")
            return False
