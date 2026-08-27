import datetime
import json
import os
from pathlib import Path


class ReportEngine:
    def __init__(
        self,
        report_path="DAILY_LEADS.md",
        state_path=None,
    ):
        # 强制使用基于脚本位置的绝对路径
        current_file_dir = Path(__file__).parent.absolute()
        if state_path is None:
            self.state_path = current_file_dir / "processed_tasks.json"
        else:
            self.state_path = Path(state_path)

        self.report_path = current_file_dir.parent.parent / report_path
        self.load_state()
        self.init_report()

    def load_state(self):
        if self.state_path.exists():
            with open(self.state_path, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        else:
            self.state = {"processed_files": []}

    def save_state(self, file_name):
        self.state["processed_files"].append(file_name)
        # 仅保留最近 1000 条记录防止文件过大
        if len(self.state["processed_files"]) > 1000:
            self.state["processed_files"] = self.state["processed_files"][-1000:]
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def init_report(self):
        if not self.report_path.exists():
            with open(self.report_path, "w", encoding="utf-8") as f:
                f.write("# 🚀 派单实时研判库 (自动更新)\n\n")
                f.write(
                    f"> 监控启动时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                )
                f.write("---\n\n")

    def append_lead(self, file_name, notification_text):
        """将研判结果追加到 Markdown 报告中"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        with open(self.report_path, "a", encoding="utf-8") as f:
            f.write(f"## 🕒 [{timestamp}] 拦截到新任务: `{file_name}`\n\n")
            f.write(notification_text + "\n\n")
            f.write("---\n\n")

        self.save_state(file_name)
        print(f"[√] 报告已更新: {self.report_path}")

    def is_processed(self, file_name):
        return file_name in self.state["processed_files"]
