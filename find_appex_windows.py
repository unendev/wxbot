import win32gui
import win32process
import psutil

def get_appex_windows():
    appex_pids = set()
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and proc.info['name'].lower() == 'wechatappex.exe':
            appex_pids.add(proc.info['pid'])
            
    print(f"当前运行的 WeChatAppEx.exe 进程 PIDs: {appex_pids}")
    
    windows = []
    def enum_windows_callback(hwnd, extra):
        is_visible = win32gui.IsWindowVisible(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        if pid in appex_pids:
            windows.append({
                "hwnd": hwnd,
                "class_name": class_name,
                "title": title,
                "is_visible": is_visible,
                "pid": pid
            })
        return True
        
    win32gui.EnumWindows(enum_windows_callback, None)
    return windows

if __name__ == "__main__":
    print("扫描 WeChatAppEx.exe 的所有窗口...")
    windows = get_appex_windows()
    print(f"共发现 {len(windows)} 个相关窗口：")
    print("-" * 75)
    for win in windows:
        if win['is_visible'] or win['title']:  # 只打印可见的或有标题的
            print(f"HWND: {win['hwnd']} ({hex(win['hwnd'])}) | PID: {win['pid']} | Visible: {win['is_visible']}")
            print(f"  - Class: {win['class_name']}")
            print(f"  - Title: '{win['title']}'")
            print("-" * 75)
