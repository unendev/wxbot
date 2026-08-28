# -*- coding: utf-8 -*-
"""
微信 AI 智能助手 (基于 wechatauto-replica 4.0+ 现代化驱动)
支持多目标（群聊、私聊）全自动后台监听与 30 轮多模态独立记忆闭环
"""
import sys
import time
from pathlib import Path

# 控制台 UTF-8 编码支持
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from wechatauto import WeChat
from llm_service import call_llm

# =========================================================
# 配置区：填写需要监听的好友备注名或群聊名称
# =========================================================
LISTEN_TARGETS = ["bot", "老父亲", "测试群"]

def on_message_received(msg, chat):
    """收到新消息的回调处理函数"""
    try:
        # 排除自己发出的消息
        if getattr(msg, "is_self", False) or getattr(msg, "attr", "") == "self":
            return

        chat_name = getattr(chat, "who", "未知会话")
        sender = getattr(msg, "sender", chat_name)
        content = getattr(msg, "content", "")
        msg_type = getattr(msg, "type", "text")

        now_str = time.strftime("%H:%M:%S")
        print(f"\n[{now_str}] 收到 [{chat_name}] 成员 [{sender}] 的消息 (类型: {msg_type})")

        img_path = None
        # 如果是图片消息
        if msg_type == "image":
            print(f"[*] 正在提取图片...")
            try:
                # 尝试保存/提取图片本地路径
                if hasattr(msg, "save"):
                    saved_res = msg.save()
                    if isinstance(saved_res, (str, Path)) and Path(saved_res).exists():
                        img_path = Path(saved_res)
                        print(f"[+] 成功提取图片路径: {img_path.name}")
            except Exception as e:
                print(f"[-] 提取图片遇到异常: {e}")

            if not content:
                content = "请仔细分析这张图片的内容并给出详细专业的解答。"

        if not content:
            return

        print(f"[*] 消息内容: {content}")
        print(f"[*] 正在请求 Gemini 大脑 (当前会话: {chat_name})...")

        # 调取大模型（按 chat_name 严格隔离 30 轮上下文记忆）
        reply = call_llm(chat_name, content, image_path=img_path)

        if reply:
            print(f"[*] 正在发送回复给 [{chat_name}]...")
            chat.SendMsg(reply)
            print(f"[{now_str}] [√] 回复成功发出！")
        else:
            print(f"[-] 未获取到有效回复，跳过发送。")

    except Exception as e:
        print(f"[-] 处理消息回调异常: {e}")

def main():
    print("=" * 60)
    print(" 微信 4.0+ AI 百科全书机器人已启动 (wechatauto-replica 引擎)")
    print("=" * 60)

    try:
        # 初始化微信客户端
        wx = WeChat()
        print("[+] 成功绑定微信主进程！")
    except Exception as e:
        print(f"[-] 初始化微信失败，请确认微信已登录并运行在桌面。错误: {e}")
        return

    # 批量添加监听目标
    print(f"[*] 正在注册多目标监听器...")
    success_count = 0
    for target in LISTEN_TARGETS:
        try:
            res = wx.AddListenChat(target, on_message_received)
            print(f" [+] 已成功挂载监听: [{target}]")
            success_count += 1
        except Exception as e:
            print(f" [-] 挂载目标 [{target}] 失败 (请确认微信中是否存在此好友/群): {e}")

    if success_count == 0:
        print("[-] 没有成功挂载任何监听目标，请检查 LISTEN_TARGETS 配置。")
        return

    print("-" * 60)
    print(f"[*] 全功能监听已就绪 (成功监听 {success_count} 个目标)。")
    print("[*] 正在常驻后台运行... (按 Ctrl+C 可安全退出)")
    print("=" * 60)

    # 阻塞主线程保持运行
    try:
        wx.KeepRunning()
    except KeyboardInterrupt:
        print("\n[*] 正在退出机器人...")
        wx.StopListening(True)
        print("[*] 机器人已安全退出。")

if __name__ == "__main__":
    main()
