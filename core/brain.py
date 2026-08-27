# -*- coding: utf-8 -*-
"""
大模型决策与回复大脑 (Brain & Decision Engine)
支持群聊闲聊、派单研判与指令解析
"""
import logging
import requests
from typing import List, Dict, Optional, Tuple
from core.config import config

logger = logging.getLogger("wxbot.brain")

class DecisionBrain:
    def __init__(self, cfg=config):
        self.cfg = cfg
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

    def decide_and_reply(
        self,
        current_msg: str,
        image_text: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[str]:
        """
        根据当前消息、图片识别文字和历史记录做出判断并生成回复
        """
        if not current_msg and not image_text:
            return None

        # 拼接用户输入
        user_content = current_msg.strip()
        if image_text:
            user_content += f"\n[发送了一张图片，图片内识别文字如下]:\n{image_text}"

        system_prompt = (
            self.dispatch_prompt if self.cfg.mode == "dispatch" else self.chat_prompt
        )

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_content})

        try:
            payload = {
                "model": self.cfg.llm_model,
                "messages": messages,
                "temperature": self.cfg.llm_temperature,
            }
            headers = {
                "Authorization": f"Bearer {self.cfg.llm_api_key}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                self.cfg.llm_api_url,
                headers=headers,
                json=payload,
                timeout=15,
            )

            if response.status_code == 200:
                result = response.json()
                reply = result["choices"][0]["message"]["content"].strip()
                return reply
            else:
                logger.error(
                    f"[Brain] LLM HTTP 异常 {response.status_code}: {response.text}"
                )
                return None
        except Exception as e:
            logger.error(f"[Brain] 调用大模型失败: {e}")
            return None
