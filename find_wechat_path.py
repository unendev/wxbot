import os
from pathlib import Path

try:
    import winreg as win32reg
except ImportError:
    import win32reg


def get_wechat_doc_path():
    """通过注册表获取微信文档存储根路径"""
    try:
        key = win32reg.OpenKey(
            win32reg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat", 0, win32reg.KEY_READ
        )
        path, _ = win32reg.QueryValueEx(key, "FileSavePath")
        win32reg.CloseKey(key)
        if path == "MyDocuments":
            # 默认在我的文档
            return str(Path.home() / "Documents" / "WeChat Files")
        return str(Path(path) / "WeChat Files")
    except Exception:
        # 兜底方案
        return str(Path.home() / "Documents" / "WeChat Files")


def find_active_user_folder(base_path):
    """在所有用户文件夹中寻找最近活跃的 FileStorage"""
    if not os.path.exists(base_path):
        return None

    users = [
        d
        for d in os.listdir(base_path)
        if os.path.isdir(os.path.join(base_path, d)) and d != "All Users"
    ]

    active_paths = []
    for user in users:
        file_path = Path(base_path) / user / "FileStorage" / "File"
        if file_path.exists():
            # 获取该目录下最新的年月文件夹
            months = [m for m in os.listdir(file_path) if os.path.isdir(file_path / m)]
            if months:
                latest_month = sorted(months)[-1]
                target = file_path / latest_month
                active_paths.append((target, target.stat().st_mtime))

    if not active_paths:
        return None

    # 返回修改时间最近的路径
    return sorted(active_paths, key=lambda x: x[1], reverse=True)[0][0]


if __name__ == "__main__":
    base = get_wechat_doc_path()
    print(f"[*] 微信文档根路径: {base}")
    active = find_active_user_folder(base)
    if active:
        print(f"[+] 定位到活跃收件路径: {active}")
    else:
        print("[-] 未发现活跃的文件收发目录，请确认微信已接收过文件。")
