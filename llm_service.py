# -*- coding: utf-8 -*-
"""
大模型对话服务与多会话记忆隔离管理 (统一兼容层)
支持特性：
1. 双协议支持：OpenAI 兼容接口 (LLM_API_URL / 本地代理) 与 Google 官方接口 (GEMINI_API_KEY)
2. 多模态原生视觉图文输入 (Base64 inline_data / image_url)
3. 30 轮多会话严格隔离滑动记忆池 (FIFO)
4. 微信纯文本输出清洗
5. 工业级标准 Logging
"""
import os
import re
import time
import base64
import logging
from pathlib import Path
import requests
from dotenv import load_dotenv

logger = logging.getLogger("wxbot.llm")

# 加载 .env
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

LLM_API_URL = os.getenv("LLM_API_URL", "").strip()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite").strip()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com").rstrip("/")

MAX_HISTORY_TURNS = 30
SESSION_TIMEOUT_SECONDS = 1800
memory_pool = {}

def clean_markdown_to_text(md_text: str) -> str:
    """终极 Markdown 清洗转换器：彻底剔除引用符(>)、粗斜体(**)、代码块(```)、标题(#)等所有标记"""
    if not md_text:
        return ""
    t = md_text
    # 1. 移除代码块标记 (保留代码块内文字)
    t = re.sub(r"```[\w]*\n?([\s\S]*?)```", r"\1", t)
    # 2. 移除行内代码 `code`
    t = re.sub(r"`([^`]+)`", r"\1", t)
    # 3. 移除粗体、斜体、删除线 **text**, *text*, ~~text~~, __text__
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"__([^_]+)__", r"\1", t)
    t = re.sub(r"~~([^~]+)~~", r"\1", t)
    # 4. 移除标题符号 # Header
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.MULTILINE)
    # 5. 移除 Markdown 引用符号 > Blockquote (核心修复)
    t = re.sub(r"^\s*>\s*", "", t, flags=re.MULTILINE)
    # 6. 移除无序列表符号 - list, * list, + list
    t = re.sub(r"^\s*[-*+]\s+", "", t, flags=re.MULTILINE)
    # 7. 移除分割线 ---, ***, ___
    t = re.sub(r"^\s*[-*_]{3,}\s*$", "", t, flags=re.MULTILINE)
    # 8. 移除超链接 [text](url) -> text, ![img](url) -> ""
    t = re.sub(r"!\[(.*?)\]\(.*?\)", r"\1", t)
    t = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", t)
    # 9. 压缩多余空行
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def get_or_create_session(chat_name: str) -> list:
    now = time.time()
    if chat_name in memory_pool:
        session_data = memory_pool[chat_name]
        if now - session_data["last_time"] > SESSION_TIMEOUT_SECONDS:
            logger.info("Session '%s' expired (>30m inactive), resetting memory context", chat_name)
            memory_pool[chat_name] = {"history": [], "last_time": now}
        else:
            session_data["last_time"] = now
    else:
        memory_pool[chat_name] = {"history": [], "last_time": now}
    return memory_pool[chat_name]["history"]

def call_llm(chat_name: str, user_prompt: str, image_path: Path = None) -> str:
    history = get_or_create_session(chat_name)

    # 1. 优先使用 OpenAI 兼容模式 (LLM_API_URL)
    if LLM_API_URL:
        user_content = []
        if image_path and image_path.exists():
            try:
                with open(image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
            except Exception as e:
                logger.warning("[%s] Failed to encode image: %s", chat_name, e)

        if user_prompt:
            user_content.append({"type": "text", "text": user_prompt})

        if not user_content:
            return ""

        # 兼容简易单文本形式
        final_user_msg = user_prompt if (len(user_content) == 1 and not image_path) else user_content

        # 微信即时聊天字数与精炼度规范 (不限制说话风格与人设，仅约束字数长度，避免冗长)
        system_brevity_rule = {
            "role": "system",
            "content": "【微信即时聊天字数规范】：回复请保持精炼，日常交流通常控制在 50~100 字以内（言简意赅，不要长篇大论）。唯有在用户明确要求详细分析、总结长文或编写代码时，方可按需展开长篇回复。"
        }

        messages = [system_brevity_rule] + history + [{"role": "user", "content": final_user_msg}]
        payload = {
            "model": LLM_MODEL,
            "messages": messages,
            "temperature": 0.7
        }
        headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}

        t0 = time.time()
        try:
            resp = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=45)
            cost = time.time() - t0
            if resp.status_code == 200:
                raw_text = resp.json()["choices"][0]["message"]["content"].strip()
                clean_reply = clean_markdown_to_text(raw_text)

                history.append({"role": "user", "content": final_user_msg})
                history.append({"role": "assistant", "content": clean_reply})
                if len(history) > MAX_HISTORY_TURNS * 2:
                    history = history[-MAX_HISTORY_TURNS * 2:]
                    memory_pool[chat_name]["history"] = history

                logger.info("[%s] LLM generation succeeded (duration: %.2fs, memory: %d/%d)", chat_name, cost, len(history)//2, MAX_HISTORY_TURNS)
                return clean_reply
            else:
                logger.error("[%s] LLM API returned HTTP %d: %s", chat_name, resp.status_code, resp.text)
                return f"【服务异常】大模型返回 HTTP {resp.status_code}"
        except Exception as e:
            logger.error("[%s] LLM request exception: %s", chat_name, e)
            return "大模型连接超时，请稍后再试。"

    # 2. 官方 Google Gemini 协议
    elif GEMINI_API_KEY:
        url = f"{GEMINI_BASE_URL}/v1beta/models/{LLM_MODEL or 'gemini-2.0-flash'}:generateContent?key={GEMINI_API_KEY}"
        user_parts = []
        if image_path and image_path.exists():
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            user_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
        if user_prompt:
            user_parts.append({"text": user_prompt})

        contents = list(history) + [{"role": "user", "parts": user_parts}]
        payload = {
            "contents": contents,
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}
        }
        t0 = time.time()
        try:
            resp = requests.post(url, json=payload, timeout=45)
            cost = time.time() - t0
            if resp.status_code == 200:
                raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                clean_reply = clean_markdown_to_text(raw_text)
                history.append({"role": "user", "parts": user_parts})
                history.append({"role": "model", "parts": [{"text": clean_reply}]})
                if len(history) > MAX_HISTORY_TURNS * 2:
                    history = history[-MAX_HISTORY_TURNS * 2:]
                    memory_pool[chat_name]["history"] = history
                logger.info("[%s] LLM generation succeeded (duration: %.2fs, memory: %d/%d)", chat_name, cost, len(history)//2, MAX_HISTORY_TURNS)
                return clean_reply
            else:
                logger.error("[%s] Gemini API returned HTTP %d: %s", chat_name, resp.status_code, resp.text)
                return f"【服务异常】Gemini API 返回 HTTP {resp.status_code}"
        except Exception as e:
            logger.error("[%s] Gemini request exception: %s", chat_name, e)
            return "大模型连接超时，请稍后再试。"

    else:
        logger.error("No LLM configuration found in .env")
        return "【系统提示】尚未配置大模型 API，请检查 .env 文件。"
