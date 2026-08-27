# -*- coding: utf-8 -*-
"""
微信智能机器人主编排中枢 (Industrial Producer-Consumer Orchestrator)
架构模式:
1. Watcher (生产者线程): 毫秒级无阻塞监听尾部游标 (High-Water Mark)
2. Worker (消费者线程): 消费队列消息 -> 防抖合并 -> LLM 推理 -> 静默发送
3. Storage (持久化层): 逻辑指纹去重与断路保护
"""
import logging
import os
import queue
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import List

# 设置编码与工作目录
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
os.chdir(CURRENT_DIR)

from core.config import config
from core.domain import ChatMessage, BotReply
from core.storage import MessageRepository
from core.brain import DecisionBrain
from core.ocr_engine import OCREngine
from core.wechat_driver import WeChatDriver

# 日志初始化
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.log_path, encoding="utf-8"),
    ],
)
logger = logging.getLogger("wxbot.main")

class WeChatBotEngine:
    def __init__(self):
        self.cfg = config
        self.storage = MessageRepository(self.cfg.db_path)
        self.brain = DecisionBrain(self.cfg)
        self.ocr = OCREngine(enabled=self.cfg.enable_ocr)
        self.driver = WeChatDriver(self.cfg)

        self.event_queue = queue.Queue()
        self.running = False
        self._watcher_thread = None
        self._worker_thread = None

    def start(self):
        self.running = True
        logger.info("==========================================")
        logger.info(f" 微信智能机器人引擎已启动 (工业级生产-消费架构)")
        logger.info(f" 目标会话: {self.cfg.target_chat} | 机器人名: {self.cfg.bot_name}")
        logger.info(f" 模型: {self.cfg.llm_model} | OCR: {'启用' if self.cfg.enable_ocr else '关闭'}")
        logger.info("==========================================")

        self.storage.cleanup_old_records()

        # 启动生产者和消费者工作线程
        self._watcher_thread = threading.Thread(target=self._watcher_loop, daemon=True)
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)

        self._watcher_thread.start()
        self._worker_thread.start()

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到退出信号，系统安全停机中...")
            self.running = False

    def _watcher_loop(self):
        """生产者线程：轻量监听微信尾部游标变动，无阻塞产生事件"""
        last_known_fp = None
        initialized_baseline = False

        while self.running:
            try:
                if not self.driver.find_wechat_window():
                    time.sleep(1.0)
                    continue

                tail_messages = self.driver.get_tail_messages(limit=5)
                if not tail_messages:
                    time.sleep(0.5)
                    continue

                # 冷启动第一轮：将当前尾部最后一条消息作为高水位游标基线，跳过历史消息
                if not initialized_baseline:
                    last_msg = tail_messages[-1]
                    last_known_fp = last_msg.fingerprint
                    self.storage.mark_processed(last_known_fp, last_msg.content)
                    self.storage.set_cursor(self.cfg.target_chat, last_known_fp)
                    logger.info(f"[+] 冷启动已同步当前聊天尾部游标基线 (指纹: {last_known_fp})，开始监听新消息...")
                    initialized_baseline = True
                    time.sleep(0.5)
                    continue

                # 检查尾部是否有全新消息
                for msg in tail_messages:
                    fp = msg.fingerprint
                    # 过滤自身发言
                    if msg.sender_type == "bot":
                        self.storage.mark_processed(fp, msg.content)
                        continue

                    # 检查是否已消费
                    if not self.storage.is_processed(fp):
                        self.storage.mark_processed(fp, msg.content)
                        trace_id = f"trace_{uuid.uuid4().hex[:6]}"
                        logger.info(f"[{trace_id}][Watcher] 捕获到全新未读消息: {msg.content}")
                        self.event_queue.put((trace_id, msg))
                        last_known_fp = fp

            except Exception as e:
                logger.error(f"[Watcher] 监听循环异常: {e}", exc_info=True)

            time.sleep(0.6)

    def _worker_loop(self):
        """消费者线程：防抖消费队列、调用大模型推理、执行静默投递"""
        while self.running:
            try:
                # 阻塞获取第一条新消息
                trace_id, first_msg = self.event_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            # 防抖合并 (Debounce/Batching)：若短时间内有连续多条消息，合并打包处理
            batch_messages = [first_msg]
            time.sleep(0.8)  # 等待 800ms 观察是否有连发短句
            while not self.event_queue.empty():
                try:
                    _, extra_msg = self.event_queue.get_nowait()
                    batch_messages.append(extra_msg)
                except queue.Empty:
                    break

            try:
                # 调用决策大脑生成回复
                reply = self.brain.generate_reply(
                    messages=batch_messages,
                    trace_id=trace_id
                )

                # 执行静默发送
                if reply and reply.content:
                    sent = self.driver.send_text_silent(reply.content)
                    if sent:
                        logger.info(f"[{trace_id}][Dispatcher] 消息已在后台成功送达并发出")
            except Exception as e:
                logger.error(f"[{trace_id}][Worker] 消费处理异常: {e}", exc_info=True)

def main():
    bot = WeChatBotEngine()
    bot.start()

if __name__ == "__main__":
    main()
