# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock
from core.brain import DecisionBrain
from core.config import BotConfig
from core.domain import ChatMessage

class TestBrain(unittest.TestCase):
    def setUp(self):
        self.cfg = BotConfig()
        self.brain = DecisionBrain(self.cfg)

    def test_empty_messages_returns_none(self):
        res = self.brain.generate_reply([])
        self.assertIsNone(res)

    @patch("requests.post")
    def test_successful_generation(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "今天天气很好 [微笑]"}}]
        }
        mock_post.return_value = mock_resp

        messages = [ChatMessage(content="今天天气怎么样？")]
        res = self.brain.generate_reply(messages)
        self.assertIsNotNone(res)
        self.assertEqual(res.content, "今天天气很好 [微笑]")

    @patch("requests.post")
    def test_circuit_breaker(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_post.return_value = mock_resp

        msg = [ChatMessage(content="测试")]
        # 触发 3 次失败
        self.brain.generate_reply(msg)
        self.brain.generate_reply(msg)
        self.brain.generate_reply(msg)

        # 断路器开启
        self.assertTrue(self.brain.is_circuit_open())

if __name__ == "__main__":
    unittest.main()
