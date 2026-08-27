# -*- coding: utf-8 -*-
"""
数据存储与去重模块 (Storage & Deduplication)
"""
import sqlite3
import time
from pathlib import Path
from typing import Union
from contextlib import contextmanager

class MessageRepository:
    def __init__(self, db_path: Union[str, Path] = "processed_orders.db"):
        self.db_path = str(db_path)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_messages (
                    id TEXT PRIMARY KEY,
                    timestamp REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def is_processed(self, msg_id: str) -> bool:
        """检查消息是否已被消费"""
        if not msg_id:
            return False
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM processed_messages WHERE id = ?", (msg_id,)
            )
            return cursor.fetchone() is not None

    def mark_processed(self, msg_id: str):
        """将消息标记为已消费"""
        if not msg_id:
            return
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO processed_messages (id, timestamp) VALUES (?, ?)",
                (msg_id, time.time()),
            )

    def cleanup_old_records(self, max_age_days: int = 7):
        """定期清理过期历史记录以防止数据库膨胀"""
        cutoff = time.time() - (max_age_days * 86400)
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM processed_messages WHERE timestamp < ?", (cutoff,)
            )

    def clear_all(self):
        """清空数据表 (仅供测试或重置使用)"""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM processed_messages")
