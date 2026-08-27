# -*- coding: utf-8 -*-
"""
会话上下文管理器 (Session Context Manager)
业界标准设计：
1. 会话隔离 (Session Isolation)
2. 15分钟 TTL 时间衰减 (自动识别新话题，清理过期记忆)
3. 滑动窗口限制 (Sliding Window，默认保留最近 10 轮)
"""
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class SessionMemory:
    session_id: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    last_active_at: float = field(default_factory=time.time)

class ContextManager:
    def __init__(self, max_history_turns: int = 10, ttl_seconds: float = 900.0):
        self.max_history_turns = max_history_turns
        self.ttl_seconds = ttl_seconds  # 默认 15 分钟超时
        self._sessions: Dict[str, SessionMemory] = {}

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """获取指定会话的有效历史上下文"""
        now = time.time()
        session = self._sessions.get(session_id)
        if not session:
            return []

        # 检查 TTL 时间衰减
        if now - session.last_active_at > self.ttl_seconds:
            # 超过 15 分钟未活动，视作新话题，清空旧记忆
            session.messages.clear()
            session.last_active_at = now
            return []

        return list(session.messages)

    def append_user_message(self, session_id: str, content: str):
        """记录用户发言"""
        session = self._get_or_create_session(session_id)
        session.messages.append({"role": "user", "content": content})
        self._trim_history(session)
        session.last_active_at = time.time()

    def append_bot_reply(self, session_id: str, content: str):
        """记录机器人自身回复"""
        session = self._get_or_create_session(session_id)
        session.messages.append({"role": "assistant", "content": content})
        self._trim_history(session)
        session.last_active_at = time.time()

    def clear_session(self, session_id: str):
        """显式清空指定会话的上下文"""
        if session_id in self._sessions:
            self._sessions[session_id].messages.clear()

    def _get_or_create_session(self, session_id: str) -> SessionMemory:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMemory(session_id=session_id)
        return self._sessions[session_id]

    def _trim_history(self, session: SessionMemory):
        """滑动窗口裁剪：只保留最近 max_history_turns 轮 (2 * turns 条)"""
        max_items = self.max_history_turns * 2
        if len(session.messages) > max_items:
            session.messages = session.messages[-max_items:]
