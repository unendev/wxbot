import win32gui
import win32process
import psutil

def get_all_windows():
    windows = []
    def enum_windows_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                proc_name = proc.name()
            except Exception:
                proc_name = "Unknown"
            
            # 如果标题或进程名包含 WeChat 或是微信
            if "wechat" in proc_name.lower() or "微信" in title or "wechat" in title.lower() or class_name.startswith("WeChat"):
                windows.append({
                    "hwnd": hwnd,
                    "pid": pid,
                    "proc_name": proc_name,
                    "class_name": class_name,
                    "title": title
                })
        return True
    win32gui.EnumWindows(enum_windows_callback, None)
    return windows

if __name__ == "__main__":
    print("正在扫描与微信相关的可见窗口...")
    windows = get_all_windows()
    if not windows:
        print("未发现任何与微信相关的可见窗口！")
        # 顺便列一下所有名为 WeChat.exe 的进程
        print("正在检查 WeChat.exe 进程...")
        wechat_procs = []
        for proc in psutil.process_iter(['pid', 'name']):
            if 'wechat' in proc.info['name'].lower():
                wechat_procs.append(proc.info)
        if wechat_procs:
            print(f"找到以下微信进程: {wechat_procs}")
        else:
            print("未找到任何名为 WeChat.exe 的进程！")
    else:
        print(f"找到 {len(windows)} 个相关窗口：")
        for win in windows:
            print(f"HWND: {win['hwnd']} | PID: {win['pid']} ({win['proc_name']}) | Class: {win['class_name']} | Title: '{win['title']}'")
