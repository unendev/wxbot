import os
import shutil
import time
from pathlib import Path

from find_wechat_path import find_active_user_folder, get_wechat_doc_path
from processor.intelligence_core import IntelligenceEngine
from processor.report_engine import ReportEngine

# 自动发现路径逻辑
BASE_DOC_PATH = get_wechat_doc_path()
MONITOR_PATH = find_active_user_folder(BASE_DOC_PATH)

if MONITOR_PATH:
    MONITOR_PATH = str(MONITOR_PATH)
    print(f"[+] 自动锁定微信文件监控路径: {MONITOR_PATH}")
else:
    # 兜底硬编码（如果注册表失效）
    MONITOR_PATH = (
        r"C:\Users\a1634\Documents\WeChat Files\wxid_zixek3hhdfdv22\FileStorage\File"
    )
    print(f"[!] 自动寻址失败，使用兜底路径: {MONITOR_PATH}")
OUTPUT_DIR = Path("temp_files")
ALLOWED_EXTENSIONS = {".zip", ".pdf", ".docx", ".jpg", ".png", ".xlsx"}

# 初始化大脑与报告引擎
engine = IntelligenceEngine(
    api_url="http://127.0.0.1:8300/v1/chat/completions",
    api_key="sk-xxxx",  # 填入你的 Key
)
reporter = ReportEngine(report_path="DAILY_LEADS.md")

# 创建输出目录
OUTPUT_DIR.mkdir(exist_ok=True)


def get_latest_month_dir(base_path):
    """动态获取最新的年月文件夹"""
    try:
        months = [
            m
            for m in os.listdir(base_path)
            if os.path.isdir(os.path.join(base_path, m))
        ]
        if not months:
            return None
        # 排除 Temp 这种非年月格式的，或者包含 Temp
        valid_months = [m for m in months if "-" in m or m == "Temp"]
        return sorted(valid_months)[-1]
    except:
        return None


def safe_copy(src, dst):
    """尝试复制文件，处理微信锁定"""
    retry = 5
    while retry > 0:
        try:
            shutil.copy2(src, dst)
            return True
        except PermissionError:
            # 文件可能正在被微信写入锁定
            print(f"[*] 文件被锁定，正在等待微信释放... ({retry})")
            time.sleep(1)
            retry -= 1
    return False


def start_monitoring(scan_history=False):
    # 向上寻找父目录以获取所有年月文件夹
    PARENT_PATH = Path(MONITOR_PATH).parent
    print(f"[*] 文件监控引擎启动")
    print(f"[*] 当前监听: {MONITOR_PATH}")
    print(f"[*] 历史回溯模式: {'开启' if scan_history else '关闭'}")

    # 扫描目标列表
    target_dirs = [MONITOR_PATH]
    if scan_history:
        # 寻找同级的年月文件夹
        try:
            for d in os.listdir(PARENT_PATH):
                full_d = os.path.join(PARENT_PATH, d)
                if os.path.isdir(full_d) and full_d not in target_dirs:
                    target_dirs.append(full_d)
            print(f"[*] 历史回溯发现 {len(target_dirs) - 1} 个历史文件夹。")
        except Exception as e:
            print(f"[!] 扫描历史目录失败: {e}")

    processed_count = 0

    # --- 历史回溯/首轮扫描阶段 ---
    print(f"[*] 正在进行首轮全量扫描...")
    for target_dir in target_dirs:
        try:
            files = os.listdir(target_dir)
            for file_name in files:
                if not reporter.is_processed(file_name):
                    file_path = os.path.join(target_dir, file_name)
                    ext = os.path.splitext(file_name)[1].lower()

                    if ext in ALLOWED_EXTENSIONS:
                        print(f"\n[🔄 回溯历史文件] {file_name}")
                        dst_path = OUTPUT_DIR / file_name
                        if safe_copy(file_path, dst_path):
                            raw_text = engine.extract_text_from_file(dst_path)
                            if raw_text:
                                display_text = f"📄 **历史存量提取预览**:\n\n```text\n{raw_text[:500]}...\n```\n"
                                reporter.append_lead(file_name, display_text)
                                processed_count += 1
                        else:
                            # 标记已处理，避免下次又报错
                            reporter.save_state(file_name)
                    else:
                        reporter.save_state(file_name)
        except Exception as e:
            print(f"[!] 扫描目录 {target_dir} 出错: {e}")

    print(
        f"[*] 首轮扫描结束，共处理 {processed_count} 个历史文件。开始进入实时监控状态..."
    )

    try:
        while True:
            current_month = get_latest_month_dir(Path(MONITOR_PATH).parent)
            if not current_month:
                time.sleep(2)
                continue

            target_dir = os.path.join(Path(MONITOR_PATH).parent, current_month)
            try:
                files = os.listdir(target_dir)
            except:
                time.sleep(1)
                continue

            for file_name in files:
                if not reporter.is_processed(file_name):
                    file_path = os.path.join(target_dir, file_name)
                    ext = os.path.splitext(file_name)[1].lower()

                    if ext in ALLOWED_EXTENSIONS:
                        print(f"\n[🔥 截获新文件] {file_name}")
                        dst_path = OUTPUT_DIR / file_name
                        if safe_copy(file_path, dst_path):
                            raw_text = engine.extract_text_from_file(dst_path)
                            if raw_text:
                                display_text = f"📄 **原始提取内容预览**:\n\n```text\n{raw_text[:500]}...\n```\n"
                                reporter.append_lead(file_name, display_text)
                            else:
                                reporter.append_lead(file_name, "⚠️ 转译为空")
                        else:
                            reporter.save_state(file_name)
                    else:
                        reporter.save_state(file_name)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] 监控引擎已停止。")


if __name__ == "__main__":
    # 开启历史回溯模式，默认扫描所有年月目录
    start_monitoring(scan_history=True)
