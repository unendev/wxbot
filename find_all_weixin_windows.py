import win32gui
import win32process
import psutil

def get_weixin_windows():
    weixin_pids = set()
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and proc.info['name'].lower() == 'weixin.exe':
            weixin_pids.add(proc.info['pid'])
            
    windows = []
    def enum_windows_callback(hwnd, extra):
        class_name = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)
        is_visible = win32gui.IsWindowVisible(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        if pid in weixin_pids:
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
    print("扫描 Weixin.exe 的所有窗口 (无过滤)...")
    windows = get_weixin_windows()
    print(f"共发现 {len(windows)} 个窗口：")
    print("-" * 75)
    for win in windows:
        # 即使没有标题，只要类名是 Qt51514QWindowIcon 就特别关注
        is_qt_win = win['class_name'] == 'Qt51514QWindowIcon'
        print(f"HWND: {win['hwnd']} ({hex(win['hwnd'])}) | PID: {win['pid']} | Visible: {win['is_visible']} | Qt: {is_qt_win}")
        print(f"  - Class: {win['class_name']}")
        print(f"  - Title: '{win['title']}'")
        print("-" * 75)
