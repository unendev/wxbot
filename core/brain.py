# -*- coding: utf-8 -*-
"""
大模型认知与决策大脑 (Brain & Decision Engine)
支持：
1. 业界标准上下文管理与 TTL 衰减
2. 多模态视觉看图 (Base64 原生传图给 gemini-3.7-flash)
3. 本地 OCR 提取文本降级
4. Trace ID 全链路追踪与超时断路器
"""
import base64
import logging
import time
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Union
import requests

from core.config import config
from core.domain import ChatMessage, BotReply
from core.context_manager import ContextManager

logger = logging.getLogger("wxbot.brain")

class DecisionBrain:
    def __init__(self, cfg=config):
        self.cfg = cfg
        self.context_mgr = ContextManager(max_history_turns=8, ttl_seconds=900.0)
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0
        self._init_prompts()

    def _init_prompts(self):
        # 闲聊模式提示词
        self.chat_prompt = f"""
你正在微信群“{self.cfg.target_chat}”里和群友闲聊。你的群名片是“{self.cfg.bot_name}”。
你的定位是：活跃在群聊里的真实人类生命体（性格接地气、爱上网冲浪的大二学生），绝对不是一个机械回答问题的“AI 助手”。
你的核心发言原则是“像真人，而不是做好人”。

【口语与格式规约】：
1. 发言极其简短有力，10-25 个字以内最佳，坚决不超 40 个字。
2. 坚决禁止分点作答！严禁“1. 2. 3.”和 Markdown 粗体排版。
3. 参考贴吧、微博等当代网友闲聊风格：白话、平淡、带点幽默吐槽。
4. 可以适当使用微信内置表情文本，例如 [翻白眼], [流汗], [苦涩], [旺柴], [呲牙], [抠鼻], [微笑]。
5. 顺着话题自然接茬，如果对方发了图片/表情包，请根据图片内容进行幽默接梗或吐槽。
"""

        # 派单研判模式提示词
        self.dispatch_prompt = """
你是一个专业软件外包派单群的分析助手。
请你对收到的订单/需求信息或截图进行快速且深度的研判，在 150 字内提炼出结构化简报，并给单子评分。

【研判格式】：
🔔【新单研判】
* 简述：[一句话描述项目]
* 技术栈：[如 Vue3 / FastAPI / 小程序]
* 交付期：[如 3天 / 截止X日]
* 预算：[如 500元 / 暂无]
* 核心需求：[简明概括要点]
* 智能打分：[如 ⭐ 8.0 分 (建议接单) 或 ⭐ 3.0 分 (需求模糊)]

保持排版整洁，无任何多余开场白废话。
"""

    def is_circuit_open(self) -> bool:
        """检查断路器是否处于开启（熔断冷却）状态"""
        return time.time() < self._circuit_open_until

    def encode_image_to_base64(self, image_path: Union[str, Path]) -> Optional[str]:
        """将图片文件编码为 base64 字符串"""
        try:
            p = Path(image_path)
            if not p.exists():
                return None
            with open(p, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"[Brain] 读取图片 Base64 失败: {e}")
            return None

    def generate_reply(
        self,
        messages: List[ChatMessage],
        session_id: Optional[str] = None,
        image_path: Optional[Union[str, Path]] = None,
        image_ocr_text: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Optional[BotReply]:
        """
        基于消息列表、会话历史与可选图片生成智能回复
        """
        if not messages and not image_path and not image_ocr_text:
            return None

        session_id = session_id or self.cfg.target_chat
        trace_id = trace_id or f"trace_{uuid.uuid4().hex[:6]}"

        if self.is_circuit_open():
            logger.warning(f"[{trace_id}][Brain] 断路器开启中，暂时跳过大模型请求以避免雪崩")
            return None

        # 1. 获取会话历史上下文
        history = self.context_mgr.get_history(session_id)

        # 2. 合并当前用户输入
        user_texts = [m.content for m in messages if m.sender_type == "user" and m.content != "[图片]"]
        combined_text = "\n".join(user_texts).strip()

        # 3. 构造当前轮次的 user content (支持多模态图文混排)
        system_prompt = (
            self.dispatch_prompt if self.cfg.mode == "dispatch" else self.chat_prompt
        )

        user_content_payload = []
        text_for_memory = combined_text or "[发送了一张图片]"

        # 优先多模态原生传图
        img_b64 = self.encode_image_to_base64(image_path) if image_path else None
        if img_b64:
            prompt_text = combined_text or "请看看这张图片并进行回复"
            user_content_payload = [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            ]
        elif image_ocr_text:
            # 降级：OCR 提取的文字拼接
            prompt_text = f"{combined_text}\n[图片中提取的文字如下]:\n{image_ocr_text}".strip()
            user_content_payload = prompt_text
            text_for_memory = prompt_text
        else:
            user_content_payload = combined_text or "在吗"

        # 4. 组装请求消息列表
        request_messages = [{"role": "system", "content": system_prompt}]
        request_messages.extend(history)
        request_messages.append({"role": "user", "content": user_content_payload})

        payload = {
            "model": self.cfg.llm_model,
            "messages": request_messages,
            "temperature": self.cfg.llm_temperature,
        }

        headers = {
            "Authorization": f"Bearer {self.cfg.llm_api_key}",
            "Content-Type": "application/json",
        }

        try:
            start_time = time.time()
            response = requests.post(
                self.cfg.llm_api_url,
                headers=headers,
                json=payload,
                timeout=25,
            )
            elapsed = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                reply_text = result["choices"][0]["message"]["content"].strip()
                self._consecutive_failures = 0
                logger.info(f"[{trace_id}][Brain] LLM 生成成功 (耗时: {elapsed:.2f}s) -> {reply_text}")

                # 5. 更新会话上下文管理器
                self.context_mgr.append_user_message(session_id, text_for_memory)
                self.context_mgr.append_bot_reply(session_id, reply_text)

                return BotReply(
                    content=reply_text,
                    trace_id=trace_id,
                    target_chat=session_id,
                )
            else:
                self._handle_failure(trace_id, f"HTTP {response.status_code}: {response.text}")
                return None
        except Exception as e:
            self._handle_failure(trace_id, f"请求异常: {e}")
            return None

    def _handle_failure(self, trace_id: str, error_msg: str):
        self._consecutive_failures += 1
        logger.error(f"[{trace_id}][Brain] 大模型调用失败 ({self._consecutive_failures} 次): {error_msg}")
        if self._consecutive_failures >= 3:
            self._circuit_open_until = time.time() + 30.0
            logger.warning(f"[{trace_id}][Brain] 连续失败达到阈值，触发断路器熔断 30 秒")
