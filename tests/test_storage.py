# -*- coding: utf-8 -*-
import unittest
import os
import tempfile
from pathlib import Path
from core.storage import MessageRepository

class TestStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_orders.db"
        self.repo = MessageRepository(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_is_processed_initially_false(self):
        self.assertFalse(self.repo.is_processed("msg_123"))

    def test_mark_and_check_processed(self):
        self.repo.mark_processed("msg_123")
        self.assertTrue(self.repo.is_processed("msg_123"))
        self.assertFalse(self.repo.is_processed("msg_456"))

    def test_clear_all(self):
        self.repo.mark_processed("msg_123")
        self.repo.clear_all()
        self.assertFalse(self.repo.is_processed("msg_123"))

if __name__ == "__main__":
    unittest.main()
