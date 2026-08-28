# -*- coding: utf-8 -*-
"""
第 3 步独立验证脚本：调用本地 gemini-3.7-flash 接口生成百科全书回答
"""
import os
import time
import requests

# 1. 读取本地 LLM 配置
LLM_API_URL = os.getenv("LLM_API_URL", "http://127.0.0.1:7860/v1/chat/completions")
LLM_API_KEY = os.getenv("LLM_API_KEY", "123456")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.7-flash")

# 2. 百科全书提示词
SYSTEM_PROMPT = """你是一个博学、严谨且语言风趣高效的百科全书知识助手。
回答原则：
1. 简明扼要，直击本质，通俗易懂；
2. 不讲无意义的废话开场白，直接给出高质量核心解答；
3. 支持 Markdown 清晰排版。
"""

test_question = "什么是量子纠缠？请用一句话通俗解释，并举一个生活中的生动比喻。"

print("=" * 50)
print(f" [*] 第 3 步测试：正在请求本地大模型 ({LLM_MODEL})...")
print(f" [*] 提问内容: {test_question}")
print("=" * 50)

payload = {
    "model": LLM_MODEL,
    "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": test_question}
    ],
    "temperature": 0.7
}

headers = {
    "Authorization": f"Bearer {LLM_API_KEY}",
    "Content-Type": "application/json"
}

start_t = time.time()
try:
    resp = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=15)
    cost = time.time() - start_t
    
    if resp.status_code == 200:
        result = resp.json()
        reply_content = result["choices"][0]["message"]["content"].strip()
        print(f"[+] 大模型生成成功 (耗时: {cost:.2f}s)！")
        print("-" * 50)
        print(reply_content)
        print("=" * 50)
    else:
        print(f"[-] 请求失败，HTTP 状态码: {resp.status_code}")
        print(f"[-] 错误详情: {resp.text}")
except Exception as e:
    print(f"[-] 连接大模型异常: {e}")
