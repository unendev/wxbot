# -*- coding: utf-8 -*-
import unittest
import time
from core.context_manager import ContextManager

class TestContextManager(unittest.TestCase):
    def test_session_isolation(self):
        cm = ContextManager(max_history_turns=5, ttl_seconds=60.0)
        cm.append_user_message("session_a", "A 的问题")
        cm.append_user_message("session_b", "B 的问题")

        hist_a = cm.get_history("session_a")
        hist_b = cm.get_history("session_b")

        self.assertEqual(len(hist_a), 1)
        self.assertEqual(hist_a[0]["content"], "A 的问题")
        self.assertEqual(len(hist_b), 1)
        self.assertEqual(hist_b[0]["content"], "B 的问题")

    def test_sliding_window_limit(self):
        cm = ContextManager(max_history_turns=2, ttl_seconds=60.0)
        # 存入 3 轮 (6 条消息)
        for i in range(3):
            cm.append_user_message("s1", f"Q{i}")
            cm.append_bot_reply("s1", f"A{i}")

        hist = cm.get_history("s1")
        # 最多保留 2 轮 (4 条)
        self.assertEqual(len(hist), 4)
        self.assertEqual(hist[0]["content"], "Q1")
        self.assertEqual(hist[-1]["content"], "A2")

    def test_ttl_decay(self):
        cm = ContextManager(max_history_turns=5, ttl_seconds=0.1)
        cm.append_user_message("s1", "旧话题")
        time.sleep(0.15)
        # 超时后应自动清空
        hist = cm.get_history("s1")
        self.assertEqual(len(hist), 0)

if __name__ == "__main__":
    unittest.main()
