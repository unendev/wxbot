# -*- coding: utf-8 -*-
"""
大模型认知与决策大脑 (Brain & Decision Engine)
支持 Trace ID 链路追踪、超时断路器与智能多消息合并
"""
import logging
import time
import uuid
import requests
from typing import List, Dict, Optional
from core.config import config
from core.domain import ChatMessage, BotReply

logger = logging.getLogger("wxbot.brain")

class DecisionBrain:
    def __init__(self, cfg=config):
        self.cfg = cfg
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
5. 顺着话题自然接茬，不要总是复述或强调自己被 @ 了。
"""

        # 派单研判模式提示词
        self.dispatch_prompt = """
你是一个专业软件外包派单群的分析助手。
请你对收到的订单/需求信息进行快速且深度的研判，在 150 字内提炼出结构化简报，并给单子评分。

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

    def generate_reply(
        self,
        messages: List[ChatMessage],
        trace_id: Optional[str] = None,
        image_text: Optional[str] = None,
    ) -> Optional[BotReply]:
        """
        基于消息列表生成回复（支持单条或短时间多条连发合并）
        """
        if not messages:
            return None

        trace_id = trace_id or f"trace_{uuid.uuid4().hex[:8]}"

        if self.is_circuit_open():
            logger.warning(f"[{trace_id}][Brain] 断路器开启中，暂时跳过大模型请求以避免雪崩")
            return None

        # 合并用户输入内容
        user_texts = [m.content for m in messages if m.sender_type == "user"]
        if not user_texts and not image_text:
            return None

        combined_content = "\n".join(user_texts)
        if image_text:
            combined_content += f"\n[发送了一张图片，图片内识别文字如下]:\n{image_text}"

        system_prompt = (
            self.dispatch_prompt if self.cfg.mode == "dispatch" else self.chat_prompt
        )

        payload = {
            "model": self.cfg.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": combined_content},
            ],
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
                return BotReply(
                    content=reply_text,
                    trace_id=trace_id,
                    target_chat=self.cfg.target_chat,
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
