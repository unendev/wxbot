# -*- coding: utf-8 -*-
"""
领域模型与实体 (Domain Entities)
纯业务逻辑定义，不依赖任何第三方 UI 库
"""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional

@dataclass(frozen=True)
class ChatMessage:
    content: str
    sender_type: str = "user"    # "user" | "bot" | "system"
    msg_type: str = "text"       # "text" | "image"
    created_at: float = field(default_factory=time.time)

    @property
    def fingerprint(self) -> str:
        """
        基于逻辑内容的唯一指纹 (不依赖 UI 物理坐标)
        """
        raw = f"{self.sender_type}:{self.msg_type}:{self.content.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

@dataclass
class BotReply:
    content: str
    trace_id: str
    target_chat: str
    created_at: float = field(default_factory=time.time)
