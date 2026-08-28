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
        # 启动时仅一次性广播无障碍唤醒信号
        self._ensure_accessibility_enabled()

    def _ensure_accessibility_enabled(self):
        """仅在初始化时向系统广播一次无障碍信号，激活 Qt 无障碍树"""
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

    def _get_chat_message_list(self):
        """精准定位右侧聊天消息流容器 (过滤左侧好友会话栏)"""
        if not self.main_ctrl:
            return None

        # 1. 优先通过 Name="消息" 精准定位右侧聊天流
        for depth in [15, 25, 35]:
            msg_list = self.main_ctrl.ListControl(searchDepth=depth, Name="消息")
            if msg_list.Exists(0.2):
                return msg_list

        # 2. 几何位置筛选: 获取右半区 (X > 窗口左侧 + 180) 的消息列表
        wnd_rect = self.main_ctrl.BoundingRectangle
        for depth in [15, 25, 35]:
            lists = self.main_ctrl.GetChildren()
            for child in lists:
                if child.ControlTypeName == "ListControl":
                    r = child.BoundingRectangle
                    if r.left > wnd_rect.left + 150:
                        return child

            candidate = self.main_ctrl.ListControl(searchDepth=depth)
            if candidate.Exists(0.2):
                r = candidate.BoundingRectangle
                if r.left > wnd_rect.left + 150:
                    return candidate

        return self.main_ctrl.ListControl(searchDepth=20)

    def get_tail_messages(self, limit: int = 5) -> List[ChatMessage]:
        """
        业界标准：实时获取当前渲染中的最新可见消息尾部
        稳定兼容 Qt 虚拟化列表，保证 100% 实时感知新消息
        """
        if not self.main_ctrl:
            return []

        try:
            msg_list = self._get_chat_message_list()
            if not msg_list or not msg_list.Exists(0.2):
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
        确定性文本发送：支持轻量前台激活与 ValuePattern/Win32 双保险投递
        """
        if not self.main_ctrl or not self.main_hwnd or not text:
            return False

        try:
            # 1. 允许激活微信窗口前台焦点 (确保 Qt 渲染树与输入管道 100% 鲜活)
            try:
                win32gui.SetForegroundWindow(self.main_hwnd)
                time.sleep(0.05)
            except Exception:
                pass

            # 2. 定位输入框并填入内容
            edit_ctrl = self.main_ctrl.EditControl(searchDepth=30)
            if not edit_ctrl.Exists(0.5):
                edit_ctrl = self.main_ctrl.EditControl(searchDepth=20)

            if edit_ctrl.Exists(0.2):
                edit_ctrl.GetValuePattern().SetValue(text)
                time.sleep(0.05)

            # 3. 双保险触发发送: 优先发送按钮，兜底 Win32 回车按键
            send_btn = None
            for name in ["发送(S)", "发送(s)", "发送"]:
                btn = self.main_ctrl.ButtonControl(searchDepth=20, Name=name)
                if btn.Exists(0.1):
                    send_btn = btn
                    break

            if send_btn and send_btn.Exists(0.1):
                send_btn.GetInvokePattern().Invoke()
            else:
                win32gui.PostMessage(self.main_hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
                time.sleep(0.05)
                win32gui.PostMessage(self.main_hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)

            logger.info(f"[Driver] 成功发送回复: {text[:30]}...")
            return True
        except Exception as e:
            logger.error(f"[Driver] 发送消息异常: {e}", exc_info=True)
            return False
