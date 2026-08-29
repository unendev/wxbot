# -*- coding: utf-8 -*-
import os
import time
import requests
from dotenv import load_dotenv

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

LLM_API_URL = os.getenv("LLM_API_URL", "http://127.0.0.1:7860/v1/chat/completions")
LLM_API_KEY = os.getenv("LLM_API_KEY", "123456")
model_to_test = "gemini-3.5-flash-lite-search"

print(f"[*] 目标地址: {LLM_API_URL}")
print(f"[*] 测试模型: {model_to_test}")

test_prompt = "请联网搜索查询：今天（2026年8月29日）人民币对美元的参考汇率大约是多少？并给出你搜索到的来源或数据依据。"


payload = {
    "model": model_to_test,
    "messages": [
        {"role": "user", "content": test_prompt}
    ],
    "temperature": 0.7
}

headers = {
    "Authorization": f"Bearer {LLM_API_KEY}",
    "Content-Type": "application/json"
}

t0 = time.time()
try:
    print("[*] 正在发送测试请求，等待 AI Studio 响应并执行联网搜索...")
    resp = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=60)
    cost = time.time() - t0
    print(f"[*] 响应状态码: {resp.status_code}, 耗时: {cost:.2f}s")
    if resp.status_code == 200:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        print("\n" + "="*60)
        print("【大模型回复结果】:")
        print("="*60)
        print(content)
        print("="*60)
    else:
        print(f"[-] 请求返回错误: {resp.status_code} - {resp.text}")
except Exception as e:
    print(f"[-] 请求异常: {e}")
