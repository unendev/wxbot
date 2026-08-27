import win32gui
import sys

def list_child_windows(parent_hwnd):
    print(f"正在扫描父窗口 HWND: {parent_hwnd} ({hex(parent_hwnd)}) 的所有子窗口...")
    children = []
    
    def enum_child_callback(hwnd, extra):
        class_name = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)
        children.append({
            "hwnd": hwnd,
            "class_name": class_name,
            "title": title
        })
        return True
        
    try:
        win32gui.EnumChildWindows(parent_hwnd, enum_child_callback, None)
    except Exception as e:
        print(f"扫描出错: {e}")
        return
        
    print(f"共发现 {len(children)} 个子窗口句柄:")
    print("-" * 60)
    for idx, child in enumerate(children):
        print(f"  [{idx}] HWND: {child['hwnd']} ({hex(child['hwnd'])})")
        print(f"      - Class: '{child['class_name']}'")
        print(f"      - Title: '{child['title']}'")
        print("-" * 60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python list_child_hwnds.py <HWND>")
        sys.exit(1)
    hwnd = int(sys.argv[1])
    list_child_windows(hwnd)
