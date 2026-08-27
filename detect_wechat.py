import win32gui
import win32process
import uiautomation as auto
import sys

def get_wechat_windows():
    windows = []
    def enum_windows_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            # 微信主窗口类名是 WeChatMainWndForPC
            if class_name == "WeChatMainWndForPC":
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                windows.append({
                    "hwnd": hwnd,
                    "pid": pid,
                    "title": title
                })
        return True
    
    win32gui.EnumWindows(enum_windows_callback, None)
    return windows

if __name__ == "__main__":
    print("Python interpreter:", sys.executable)
    print("正在扫描系统中的微信窗口...")
    windows = get_wechat_windows()
    if not windows:
        print("未发现运行中的微信窗口(WeChatMainWndForPC)！请确保微信已启动且未完全关闭。")
    else:
        print(f"\n共发现 {len(windows)} 个微信窗口实例：")
        print("-" * 60)
        for idx, win in enumerate(windows):
            print(f"实例 [{idx}]:")
            print(f"  - 窗口句柄 (HWND): {win['hwnd']} ({hex(win['hwnd'])})")
            print(f"  - 进程 PID: {win['pid']}")
            print(f"  - 窗口标题: '{win['title']}'")
            print("-" * 60)
            
            # 尝试通过句柄读取 UIAutomation 的基本属性，看是否能绑定
            try:
                ctrl = auto.ControlFromHWND(win['hwnd'])
                # 读取窗口名
                print(f"  - UIAutomation 绑定成功，对应控件名: '{ctrl.Name}'")
            except Exception as e:
                print(f"  - UIAutomation 绑定失败: {e}")
            print("-" * 60)
