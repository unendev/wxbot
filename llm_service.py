# -*- coding: utf-8 -*-
"""
大模型对话服务与多会话记忆隔离管理
"""
import os
import re
import time
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

LLM_API_URL = os.getenv("LLM_API_URL", "http://127.0.0.1:7860/v1/chat/completions")
LLM_API_KEY = os.getenv("LLM_API_KEY", "123456")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

SYSTEM_PROMPT = """请回答用户的问题。
【排版要求】：
1. 严禁使用任何 Markdown 格式符号（严禁使用 ** 加粗、# 标题、* 列表、--- 分割线）；
2. 请使用标准换行、空行或数字序号进行纯文本排版。
"""

MAX_HISTORY_TURNS = 30
# 字典管理多会话的记忆池 { "chat_name": (last_active_time, [{"role": "user", "content": "..."}]) }
memory_pool = {}

def clean_markdown_to_text(text: str) -> str:
    """过滤 Markdown 标记，转为微信最佳纯文本"""
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    t = re.sub(r"\*([^*]+)\*", r"\1", text)
    t = re.sub(r"__([^_]+)__", r"\1", text)
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"^-{3,}\s*$", "", t, flags=re.MULTILINE)
    return t.strip()

def get_session_history(chat_name: str):
    """获取指定会话的历史记录，超时30分钟自动重置"""
    now = time.time()
    if chat_name in memory_pool:
        last_active, history = memory_pool[chat_name]
        if now - last_active > 1800:
            print(f"[*] 距离与 [{chat_name}] 的上次对话已超 30 分钟，自动开启全新对话主题。")
            history = []
    else:
        history = []
    return history

def update_session_history(chat_name: str, history: list):
    """更新指定会话的历史记录与最后活跃时间"""
    if len(history) > MAX_HISTORY_TURNS * 2:
        history = history[-MAX_HISTORY_TURNS * 2:]
    memory_pool[chat_name] = (time.time(), history)

def call_llm(chat_name: str, question: str, image_path: Path = None) -> str:
    """调用大模型生成回答 (支持纯文本与原生视觉看图，按 chat_name 隔离记忆)"""
    history = get_session_history(chat_name)

    if image_path and image_path.exists():
        print(f"[*] 正在为 Gemini 视觉大脑编码图片: {image_path.name}")
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        user_content = [
            {"type": "text", "text": question or "请仔细分析这张图片的内容并给出详细专业的解答。"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}}
        ]
    else:
        user_content = question

    history.append({"role": "user", "content": user_content})
    update_session_history(chat_name, history)

    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history,
        "temperature": 0.7
    }
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}

    start_t = time.time()
    try:
        resp = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=30)
        cost = time.time() - start_t
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            clean_content = clean_markdown_to_text(content)
            
            history.append({"role": "assistant", "content": clean_content})
            update_session_history(chat_name, history)
            
            print(f"[+] [{chat_name}] 大模型生成成功 (耗时: {cost:.2f}s, 当前记忆: {len(history)//2}/{MAX_HISTORY_TURNS})")
            return clean_content
        else:
            print(f"[-] [{chat_name}] 大模型返回错误 HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        cost = time.time() - start_t
        print(f"[-] [{chat_name}] 请求大模型异常 (耗时: {cost:.2f}s): {e}")

    return ""
