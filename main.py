# -*- coding: utf-8 -*-
"""
微信智能机器人主入口 (Main Entrypoint)
生命周期: 启动 -> 绑定微信 -> 跳过存量历史 -> 循环监听新消息 -> 提取/OCR -> LLM研判 -> 静默回复 -> 状态去重
"""
import logging
import os
import sys
import time
from pathlib import Path

# 设置编码与工作目录
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
os.chdir(CURRENT_DIR)

from core.config import config
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

class WeChatBot:
    def __init__(self):
        self.cfg = config
        self.storage = MessageRepository(self.cfg.db_path)
        self.brain = DecisionBrain(self.cfg)
        self.ocr = OCREngine(enabled=self.cfg.enable_ocr)
        self.driver = WeChatDriver(self.cfg)
        self._running = False
        self._last_bind_status = False
        self._initialized_history = False

    def start(self):
        self._running = True
        logger.info("==========================================")
        logger.info(f" 微信智能机器人启动 [模式: {self.cfg.mode}]")
        logger.info(f" 目标会话: {self.cfg.target_chat} | 机器人名: {self.cfg.bot_name}")
        logger.info(f" 模型: {self.cfg.llm_model} | OCR: {'启用' if self.cfg.enable_ocr else '关闭'}")
        logger.info("==========================================")

        # 启动时清理 7 天前过期去重历史
        self.storage.cleanup_old_records()

        while self._running:
            try:
                self._tick()
            except KeyboardInterrupt:
                logger.info("收到退出信号，机器人正常停止。")
                break
            except Exception as e:
                logger.error(f"主循环发生未捕获异常: {e}", exc_info=True)

            time.sleep(self.cfg.poll_interval)

    def _tick(self):
        # 1. 探测微信主窗口
        if not self.driver.find_wechat_window():
            if self._last_bind_status:
                logger.warning("[-] 微信窗口连接丢失，等待重新绑定...")
                self._last_bind_status = False
                self._initialized_history = False
            return

        if not self._last_bind_status:
            logger.info(f"[+] 成功绑定微信窗口 (HWND: {self.driver.main_hwnd})")
            self._last_bind_status = True

        # 2. 静默读取当前聊天流消息
        messages = self.driver.read_visible_messages()
        if not messages:
            return

        # 3. 冷启动第一轮：将屏幕上所有既有历史记录批量标记为已读，避免重复消费旧历史
        if not self._initialized_history:
            for msg in messages:
                self.storage.mark_processed(msg["id"])
            logger.info(f"[+] 冷启动已同步跳过当前屏幕上的 {len(messages)} 条存量历史消息，开始实时监听新消息...")
            self._initialized_history = True
            return

        for msg in messages:
            msg_id = msg["id"]
            content = msg["content"]
            msg_type = msg["type"]

            # 4. 查重过滤
            if self.storage.is_processed(msg_id):
                continue

            # 5. 防自循环（如果内容由机器人自身发出，则跳过并标记）
            if content.startswith(f"{self.cfg.bot_name}:") or content.startswith(f"{self.cfg.bot_name}："):
                self.storage.mark_processed(msg_id)
                continue

            logger.info(f"[收到新消息] 类型: {msg_type} | 内容: {content}")

            image_text = None
            # 6. 图片识别逻辑 (若包含图片或为图片类型)
            if msg_type == "image" and self.cfg.enable_ocr:
                pass

            # 7. 大脑研判与生成回复
            reply = self.brain.decide_and_reply(
                current_msg=content,
                image_text=image_text
            )

            # 8. 静默发送回复
            if reply:
                logger.info(f"[AI 回复生成] -> {reply}")
                sent = self.driver.send_text_silent(reply)
                if sent:
                    logger.info("[√] 消息已静默送达微信输入框并触发发送")

            # 9. 标记为已处理
            self.storage.mark_processed(msg_id)

def main():
    bot = WeChatBot()
    bot.start()

if __name__ == "__main__":
    main()
