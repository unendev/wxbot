# -*- coding: utf-8 -*-
import unittest
from core.domain import ChatMessage, BotReply

class TestDomain(unittest.TestCase):
    def test_fingerprint_consistency(self):
        msg1 = ChatMessage(content="你好", sender_type="user", msg_type="text")
        msg2 = ChatMessage(content="你好", sender_type="user", msg_type="text")
        self.assertEqual(msg1.fingerprint, msg2.fingerprint)

    def test_fingerprint_different_for_different_senders(self):
        msg1 = ChatMessage(content="你好", sender_type="user")
        msg2 = ChatMessage(content="你好", sender_type="bot")
        self.assertNotEqual(msg1.fingerprint, msg2.fingerprint)

    def test_bot_reply_creation(self):
        reply = BotReply(content="收到！", trace_id="trace_123", target_chat="大丑")
        self.assertEqual(reply.content, "收到！")
        self.assertEqual(reply.trace_id, "trace_123")

if __name__ == "__main__":
    unittest.main()
