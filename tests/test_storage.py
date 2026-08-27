# -*- coding: utf-8 -*-
import unittest
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

    def test_fingerprint_dedup(self):
        fp = "fp_abc_123"
        self.assertFalse(self.repo.is_processed(fp))
        self.repo.mark_processed(fp, "你好")
        self.assertTrue(self.repo.is_processed(fp))

    def test_cursor_management(self):
        session = "测试群"
        self.assertIsNone(self.repo.get_cursor(session))
        self.repo.set_cursor(session, "fp_999")
        self.assertEqual(self.repo.get_cursor(session), "fp_999")

if __name__ == "__main__":
    unittest.main()
