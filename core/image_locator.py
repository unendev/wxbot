# -*- coding: utf-8 -*-
"""
微信本地落地图片定位器 (Image Locator)
负责自动检索微信在本地落盘的最新图片/截图文件
"""
import os
import time
from pathlib import Path
from typing import Optional, List

CURRENT_USER = os.environ.get("USERNAME") or os.getlogin()

class WeChatImageLocator:
    def __init__(self):
        self.candidate_roots = self._get_candidate_roots()

    def _get_candidate_roots(self) -> List[Path]:
        """获取微信本地文件可能存储的根目录清单"""
        roots = []
        user_home = Path.home()
        
        # 1. 我的文档中的 WeChat Files
        doc_roots = [
            user_home / "Documents" / "WeChat Files",
            user_home / "OneDrive" / "Documents" / "WeChat Files",
        ]
        for p in doc_roots:
            if p.exists():
                roots.append(p)

        # 2. AppData 临时缓存
        appdata_root = user_home / "AppData" / "Roaming" / "Tencent" / "WeChat"
        if appdata_root.exists():
            roots.append(appdata_root)

        return roots

    def find_latest_image(self, max_age_seconds: float = 30.0) -> Optional[Path]:
        """
        在微信缓存目录中寻找最近 max_age_seconds 秒内落盘的最新图片
        """
        now = time.time()
        latest_file = None
        latest_mtime = 0.0

        valid_extensions = {".jpg", ".jpeg", ".png", ".bmp"}

        for root_dir in self.candidate_roots:
            try:
                for dirpath, _, filenames in os.walk(root_dir):
                    # 优先在 Image, Temp, FileStorage 目录中查找
                    dir_str = dirpath.replace("\\", "/")
                    if "Image" in dir_str or "Temp" in dir_str or "FileStorage" in dir_str:
                        for fname in filenames:
                            ext = Path(fname).suffix.lower()
                            if ext in valid_extensions:
                                fpath = Path(dirpath) / fname
                                try:
                                    mtime = fpath.stat().st_mtime
                                    if mtime > latest_mtime and (now - mtime) <= max_age_seconds:
                                        latest_mtime = mtime
                                        latest_file = fpath
                                except (OSError, PermissionError):
                                    continue
            except Exception:
                continue

        return latest_file
