import hashlib
import json
import os
import re
import time
import urllib.request
import zipfile
from pathlib import Path


class IntelligenceEngine:
    def __init__(self, api_url=None, api_key=None, model="gemini-3.0-flash"):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.ocr_engine = None
        self.cache_file = Path("wxbot/processor/llm_cache.json")
        self.load_cache()

    def load_cache(self):
        if self.cache_file.exists():
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
        else:
            self.cache = {}

    def save_cache(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def get_ocr(self):
        if self.ocr_engine is None:
            from paddleocr import PaddleOCR

            self.ocr_engine = PaddleOCR(
                use_angle_cls=True, lang="ch", enable_mkldnn=False
            )
        return self.ocr_engine

    def extract_text_from_file(self, file_path):
        """核心转译逻辑：根据后缀分发处理器"""
        ext = Path(file_path).suffix.lower()
        content = ""

        try:
            if ext == ".docx":
                from docx import Document

                doc = Document(file_path)
                content = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            elif ext == ".pdf":
                import pdfplumber

                with pdfplumber.open(file_path) as pdf:
                    content = "\n".join(
                        [page.extract_text() or "" for page in pdf.pages[:10]]
                    )
            elif ext in [".jpg", ".png", ".jpeg"]:
                try:
                    ocr = self.get_ocr()
                    result = ocr.ocr(str(file_path), cls=True)
                    lines = []
                    for res in result:
                        if res:
                            for line in res:
                                lines.append(line[1][0])
                    content = "\n".join(lines)
                except Exception as e:
                    content = f"[OCR 模块未就绪]: {e}"
            elif ext == ".zip":
                with zipfile.ZipFile(file_path, "r") as z:
                    file_list = z.namelist()
                    content = (
                        f"[ZIP 压缩包结构 ({len(file_list)} 个文件)]:\n"
                        + "\n".join(file_list[:30])
                    )
                    for f in file_list:
                        if any(k in f for k in ["需求", "说明", "要求", "单子"]):
                            content += f"\n\n[发现疑似需求文档]: {f}"
            else:
                content = f"[已拦截文件，后缀: {ext}]"
        except Exception as e:
            content = f"[转译异常]: {str(e)}"

        return content.strip()

    def run_llm_analysis(self, raw_content):
        # AI 逻辑暂时跳过
        return None

    def format_notification(self, analysis_result):
        # AI 逻辑暂时跳过
        return ""
