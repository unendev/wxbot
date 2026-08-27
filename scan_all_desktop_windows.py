import win32gui
import win32process
import psutil

def get_visible_windows():
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
    print("扫描桌面上所有可见顶级窗口 (不限进程, 不限名称)...")
    windows = get_visible_windows()
    print(f"共发现 {len(windows)} 个可见顶级窗口：")
    print("-" * 80)
    for win in windows:
        try:
            is_wechat_related = "weixin" in win['proc_name'].lower() or "wechat" in win['proc_name'].lower() or "微信" in win['title'] or "weixin" in win['title'].lower()
            if is_wechat_related or win['class_name'].startswith("Chrome_Widget"):
                print(f"★ [微信/Chromium 相关] HWND: {win['hwnd']} ({hex(win['hwnd'])}) | PID: {win['pid']} ({win['proc_name']})")
                print(f"  - Class: {win['class_name']}")
                print(f"  - Title: '{win['title']}'")
                print("-" * 80)
            else:
                # 其它窗口只简要打印
                print(f"HWND: {win['hwnd']} | PID: {win['pid']} ({win['proc_name']}) | Class: {win['class_name']} | Title: '{win['title']}'")
                print("-" * 80)
        except Exception as e:
            # 如果打印中文乱码，忽略或以 repr 方式打印
            print(f"HWND: {win['hwnd']} | PID: {win['pid']} ({win['proc_name']}) | Class: {win['class_name']} | Safe Title: {repr(win['title'])}")
            print("-" * 80)
