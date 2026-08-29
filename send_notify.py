# -*- coding: utf-8 -*-
"""
微信主动推送网关通用测试/客户端工具
使用示例：
python send_notify.py "渥奇" "🎉 恭喜！Steam MOD 今日新增 15 个订阅！"
"""
import sys
import json
import requests

GATEWAY_URL = "http://192.168.50.109:5005/send"  # Zimaboard 微信网关地址

def push_wechat_message(target: str, text: str):
    payload = {
        "target": target,
        "text": text
    }
    try:
        resp = requests.post(GATEWAY_URL, json=payload, timeout=5)
        print(f"[{resp.status_code}] Response:", resp.json())
    except Exception as e:
        print("[-] Push failed:", e)

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "渥奇"
    msg = sys.argv[2] if len(sys.argv) > 2 else "🔔 微信主动推送测试：这是一条来自外部独立脚本的测试通知！"
    push_wechat_message(target, msg)
