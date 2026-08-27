# -*- coding: utf-8 -*-
"""
图像 OCR 识别引擎 (OCR Engine)
支持图片文字提取，采用惰性加载与优雅降级机制
"""
import os
import logging
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger("wxbot.ocr")

class OCREngine:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._ocr_instance = None
        self._initialized = False

    def _init_ocr(self):
        if self._initialized:
            return
        self._initialized = True
        if not self.enabled:
            return

        try:
            from paddleocr import PaddleOCR
            # 初始化 PaddleOCR（关闭冗余日志与 mkldnn 兼容性问题）
            self._ocr_instance = PaddleOCR(
                use_angle_cls=True,
                lang="ch",
                show_log=False,
                enable_mkldnn=False
            )
            logger.info("[OCR] PaddleOCR 引擎加载成功")
        except ImportError:
            logger.warning("[OCR] 未检测到 paddleocr 依赖，OCR 功能自动降级关闭")
            self._ocr_instance = None
        except Exception as e:
            logger.warning(f"[OCR] 初始化异常，已降级: {e}")
            self._ocr_instance = None

    def extract_text(self, image_path: Union[str, Path]) -> Optional[str]:
        """识别图片路径中的文字"""
        if not self.enabled:
            return None

        self._init_ocr()
        if not self._ocr_instance:
            return None

        path_str = str(image_path)
        if not os.path.exists(path_str):
            return None

        try:
            result = self._ocr_instance.ocr(path_str, cls=True)
            if not result or not result[0]:
                return None

            lines = []
            for item in result[0]:
                if len(item) >= 2 and len(item[1]) >= 1:
                    lines.append(item[1][0])

            extracted = "\n".join(lines).strip()
            return extracted if extracted else None
        except Exception as e:
            logger.error(f"[OCR] 识别图片异常 ({image_path}): {e}")
            return None
