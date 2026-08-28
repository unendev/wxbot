# -*- coding: utf-8 -*-
"""
微信智能机器人主编排中枢 (基于 10a8371 黄金实测可用版本)
"""
import logging
import os
import queue
import sys
import threading
import time
import uuid
from pathlib import Path

# 设置编码与工作目录
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
os.chdir(CURRENT_DIR)

import uiautomation as auto
from core.config import config
from core.domain import ChatMessage, BotReply
from core.storage import MessageRepository
from core.brain import DecisionBrain
from core.ocr_engine import OCREngine
from core.image_locator import WeChatImageLocator
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
        self.img_locator = WeChatImageLocator()

        self.event_queue = queue.Queue()
        self.running = False
        self._watcher_thread = None
        self._worker_thread = None

    def start(self):
        self.running = True
        logger.info("==========================================")
        logger.info(" 微信智能机器人引擎已启动 (黄金实测稳定版)")
        logger.info(f" 模型: {self.cfg.llm_model} | 视觉/OCR: {'启用' if self.cfg.enable_ocr else '关闭'}")
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
        """生产者线程：极简监听尾部消息变动"""
        with auto.UIAutomationInitializerInThread():
            driver = WeChatDriver(self.cfg)
            last_bind_state = False
            initialized_baseline = False

            while self.running:
                try:
                    if not driver.find_wechat_window():
                        if last_bind_state:
                            logger.warning("[-] 微信窗口丢失，重新等待中...")
                            last_bind_state = False
                        time.sleep(1.0)
                        continue

                    if not last_bind_state:
                        logger.info(f"[+] 成功绑定微信窗口 (HWND: {driver.main_hwnd})")
                        last_bind_state = True

                    tail_messages = driver.get_tail_messages(limit=5)
                    if not tail_messages:
                        time.sleep(0.5)
                        continue

                    # 冷启动第一轮：同步最后一条消息基线，跳过历史消息
                    if not initialized_baseline:
                        last_msg = tail_messages[-1]
                        last_known_fp = last_msg.fingerprint
                        self.storage.mark_processed(last_known_fp, last_msg.content)
                        self.storage.set_cursor("active_chat", last_known_fp)
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
                            logger.info(f"[{trace_id}][Watcher] 捕获到全新未读消息 (类型: {msg.msg_type}): {msg.content}")
                            self.event_queue.put((trace_id, msg))

                except Exception as e:
                    logger.error(f"[Watcher] 监听循环异常: {e}", exc_info=True)

                time.sleep(0.6)

    def _worker_loop(self):
        """消费者线程：防抖消费队列、图片定位与推理、执行投递"""
        with auto.UIAutomationInitializerInThread():
            driver = WeChatDriver(self.cfg)
            while self.running:
                try:
                    trace_id, first_msg = self.event_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # 防抖合并 (Debounce/Batching)
                batch_messages = [first_msg]
                time.sleep(0.8)
                while not self.event_queue.empty():
                    try:
                        _, extra_msg = self.event_queue.get_nowait()
                        batch_messages.append(extra_msg)
                    except queue.Empty:
                        break

                try:
                    has_image = any(m.msg_type == "image" or "[图片]" in m.content for m in batch_messages)
                    image_path = None
                    image_ocr_text = None

                    if has_image:
                        image_path = self.img_locator.find_latest_image(max_age_seconds=30.0)
                        if image_path:
                            logger.info(f"[{trace_id}][Vision] 锁定微信最新图片: {image_path.name}")
                            if self.cfg.enable_ocr:
                                image_ocr_text = self.ocr.extract_text(image_path)
                                if image_ocr_text:
                                    logger.info(f"[{trace_id}][OCR] 提取图片文字 ({len(image_ocr_text)} 字符)")

                    # 调用决策大脑生成回复
                    reply = self.brain.generate_reply(
                        messages=batch_messages,
                        session_id="active_chat",
                        image_path=image_path,
                        image_ocr_text=image_ocr_text,
                        trace_id=trace_id
                    )

                    # 发送回复
                    if reply and reply.content:
                        if driver.find_wechat_window():
                            sent = driver.send_text_silent(reply.content)
                            if sent:
                                bot_msg = ChatMessage(content=reply.content, sender_type="bot")
                                user_msg_mirror = ChatMessage(content=reply.content, sender_type="user")
                                self.storage.mark_processed(bot_msg.fingerprint, reply.content)
                                self.storage.mark_processed(user_msg_mirror.fingerprint, reply.content)
                                logger.info(f"[{trace_id}][Dispatcher] 消息已在后台成功送达并发出")
                except Exception as e:
                    logger.error(f"[{trace_id}][Worker] 消费处理异常: {e}", exc_info=True)

def main():
    bot = WeChatBotEngine()
    bot.start()

if __name__ == "__main__":
    main()
