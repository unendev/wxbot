# -*- coding: utf-8 -*-
"""
LLM 统一服务调用层 (Google Gemini API)
标准模块化设计：
- 严格的多会话独立上下文记忆隔离 (Per-Session Memory Pool)
- 30 轮滑动窗口上下文管理 (FIFO)
- 30 分钟无活跃自然过期
- Markdown 格式安全清洗
- 工业级标准 Logging 输出
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

# 加载 .env 环境变量
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com").rstrip("/")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# 隔离记忆池结构：{ chat_name: {"history": [ {...}, ... ], "last_time": timestamp} }
memory_pool = {}
MAX_HISTORY_TURNS = 30
SESSION_TIMEOUT_SECONDS = 1800  # 30 分钟无活跃自动重置会话

SYSTEM_INSTRUCTION = (
    "你是运行在微信上的个人 AI 智能助手。你的回答应该简洁、亲切、通俗易懂，适合微信即时通讯场景。"
    "严格要求：由于微信不支持 Markdown 语法，请不要使用任何 Markdown 加粗（**）、标题（#）、列表符号（* 或 -）等排版，输出纯文本即可。"
)

def clean_markdown_to_text(md_text: str) -> str:
    """清洗大模型输出中的 Markdown 语法，输出最适合微信阅读的纯文本"""
    if not md_text:
        return ""
    text = re.sub(r"^#{1,6}\s+", "", md_text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"~~(.*?)~~", r"\1", text)
    text = re.sub(r"```[\w]*\n([\s\S]*?)```", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def get_or_create_session(chat_name: str) -> list:
    """获取指定会话的历史记录，并执行过期重置与滑动窗口管理"""
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
    """统一调用 Gemini API 生成回答（支持纯文本与多模态图文输入）"""
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not configured in .env")
        return "【系统提示】尚未配置 GEMINI_API_KEY，请检查 .env 配置文件。"

    url = f"{GEMINI_BASE_URL}/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    history = get_or_create_session(chat_name)

    user_parts = []

    # 1. 挂载图片多模态数据
    if image_path and image_path.exists():
        try:
            with open(image_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")

            ext = image_path.suffix.lower()
            mime_type = "image/png" if ext == ".png" else "image/jpeg"

            img_part = {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": b64_data
                }
            }
            user_parts.append(img_part)
        except Exception as e:
            logger.warning("[%s] Failed to encode image '%s': %s", chat_name, image_path.name, e)

    # 2. 挂载用户提问文字
    if user_prompt:
        user_parts.append({"text": user_prompt})

    if not user_parts:
        return ""

    contents = list(history)
    contents.append({
        "role": "user",
        "parts": user_parts
    })

    payload = {
        "contents": contents,
        "system_instruction": {
            "parts": [{"text": SYSTEM_INSTRUCTION}]
        },
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        }
    }

    t0 = time.time()
    try:
        resp = requests.post(url, json=payload, timeout=45)
        cost = time.time() - t0

        if resp.status_code == 200:
            data = resp.json()
            try:
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                clean_reply = clean_markdown_to_text(raw_text)

                # 记录进上下文记忆池
                history.append({"role": "user", "parts": user_parts})
                history.append({"role": "model", "parts": [{"text": clean_reply}]})

                # 维持 30 轮滑动窗口
                if len(history) > MAX_HISTORY_TURNS * 2:
                    history = history[-MAX_HISTORY_TURNS * 2:]
                    memory_pool[chat_name]["history"] = history

                logger.info(
                    "[%s] LLM generation succeeded (duration: %.2fs, memory: %d/%d)",
                    chat_name, cost, len(history) // 2, MAX_HISTORY_TURNS
                )
                return clean_reply
            except (KeyError, IndexError) as e:
                logger.error("[%s] Failed to parse LLM response format: %s", chat_name, e)
                return "抱歉，未能正确解析回答。"
        else:
            logger.error("[%s] LLM returned HTTP %d: %s", chat_name, resp.status_code, resp.text)
            return f"【服务异常】大模型接口返回 HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        logger.error("[%s] LLM request timed out (>45s)", chat_name)
        return "请求超时，大模型正在忙碌中，请稍后再试。"
    except Exception as e:
        logger.error("[%s] LLM request exception: %s", chat_name, e)
        return f"发生未知错误: {str(e)}"
