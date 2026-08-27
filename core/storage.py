# -*- coding: utf-8 -*-
"""
数据存储与高水位游标持久化 (Storage & Cursor Persistence)
支持自动 Schema 迁移 (平滑升级旧数据库)
"""
import sqlite3
import time
from pathlib import Path
from typing import Union, Optional
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
            # 1. 检查是否存在旧表结构
            cursor = conn.execute("PRAGMA table_info(processed_messages)")
            columns = [row[1] for row in cursor.fetchall()]

            if not columns:
                # 表不存在，全新创建
                conn.execute("""
                    CREATE TABLE processed_messages (
                        fingerprint TEXT PRIMARY KEY,
                        content TEXT,
                        timestamp REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            elif "fingerprint" not in columns:
                # 存在旧表结构 (例如旧表字段为 id)，执行平滑迁移
                conn.execute("DROP TABLE IF EXISTS processed_messages_old")
                conn.execute("ALTER TABLE processed_messages RENAME TO processed_messages_old")
                conn.execute("""
                    CREATE TABLE processed_messages (
                        fingerprint TEXT PRIMARY KEY,
                        content TEXT,
                        timestamp REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # 迁移旧数据
                conn.execute("""
                    INSERT OR IGNORE INTO processed_messages (fingerprint, timestamp)
                    SELECT id, timestamp FROM processed_messages_old
                """)
                conn.execute("DROP TABLE IF EXISTS processed_messages_old")

            # 2. 游标表初始化
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_cursors (
                    session_name TEXT PRIMARY KEY,
                    last_fingerprint TEXT,
                    updated_at REAL
                )
            """)

    def is_processed(self, fingerprint: str) -> bool:
        """检查逻辑指纹是否已被消费"""
        if not fingerprint:
            return False
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM processed_messages WHERE fingerprint = ?", (fingerprint,)
            )
            return cursor.fetchone() is not None

    def mark_processed(self, fingerprint: str, content: str = ""):
        """将消息标记为已消费"""
        if not fingerprint:
            return
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO processed_messages (fingerprint, content, timestamp) VALUES (?, ?, ?)",
                (fingerprint, content[:200], time.time()),
            )

    def get_cursor(self, session_name: str) -> Optional[str]:
        """获取当前会话的高水位游标"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT last_fingerprint FROM session_cursors WHERE session_name = ?", (session_name,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def set_cursor(self, session_name: str, fingerprint: str):
        """更新会话的高水位游标"""
        if not fingerprint:
            return
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO session_cursors (session_name, last_fingerprint, updated_at) VALUES (?, ?, ?)",
                (session_name, fingerprint, time.time()),
            )

    def cleanup_old_records(self, max_age_days: int = 7):
        """定期清理过期历史记录以防止数据库膨胀"""
        cutoff = time.time() - (max_age_days * 86400)
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM processed_messages WHERE timestamp < ?", (cutoff,)
            )

    def clear_all(self):
        """清空数据表 (仅供测试使用)"""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM processed_messages")
            conn.execute("DELETE FROM session_cursors")
