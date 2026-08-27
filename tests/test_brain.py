# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock
from core.brain import DecisionBrain
from core.config import BotConfig

class TestBrain(unittest.TestCase):
    def setUp(self):
        self.cfg = BotConfig()
        self.brain = DecisionBrain(self.cfg)

    def test_empty_message_returns_none(self):
        res = self.brain.decide_and_reply("", None)
        self.assertIsNone(res)

    @patch("requests.post")
    def test_successful_reply(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "今天天气真不错 [微笑]"}}]
        }
        mock_post.return_value = mock_resp

        res = self.brain.decide_and_reply("今天天气怎么样？")
        self.assertEqual(res, "今天天气真不错 [微笑]")

    @patch("requests.post")
    def test_failed_reply_fallback(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp

        res = self.brain.decide_and_reply("你好")
        self.assertIsNone(res)

if __name__ == "__main__":
    unittest.main()
