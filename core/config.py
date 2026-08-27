# -*- coding: utf-8 -*-
"""
统一配置中心 (Config Center)
支持从 .env 读取配置，提供类型安全的默认值
"""
import os
from pathlib import Path
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent

@dataclass
class BotConfig:
    # 微信窗口与会话配置
    target_chat: str = os.getenv("WX_TARGET_CHAT", "大丑")
    bot_name: str = os.getenv("WX_BOT_NAME", "小丑")
    
    # 大语言模型配置
    llm_api_url: str = os.getenv("LLM_API_URL", "http://127.0.0.1:7860/v1/chat/completions")
    llm_api_key: str = os.getenv("LLM_API_KEY", "123456")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    
    # 运行与监听策略
    poll_interval: float = float(os.getenv("POLL_INTERVAL", "1.5"))
    enable_ocr: bool = os.getenv("ENABLE_OCR", "true").lower() in ("true", "1", "yes")
    mode: str = os.getenv("MODE", "chat")  # chat: 闲聊/对话助手, dispatch: 派单研判
    
    # 存储与日志路径
    db_path: Path = ROOT_DIR / "processed_orders.db"
    log_path: Path = ROOT_DIR / "bot.log"
    assets_dir: Path = ROOT_DIR / "assets"

config = BotConfig()
