# -*- coding: utf-8 -*-
import unittest
from core.config import BotConfig

class TestConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = BotConfig()
        self.assertIsNotNone(cfg.target_chat)
        self.assertIsNotNone(cfg.bot_name)
        self.assertIsInstance(cfg.poll_interval, float)
        self.assertIsInstance(cfg.enable_ocr, bool)

if __name__ == "__main__":
    unittest.main()
