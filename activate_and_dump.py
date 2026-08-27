import uiautomation as auto
import sys
import time
import win32gui
import win32process

def test_activate(hwnd):
    print(f"正在绑定 HWND: {hwnd}")
    try:
        ctrl = auto.ControlFromHandle(hwnd)
        print("绑定成功！")
        
        # 获取当前的活动窗口，以便测试完后把焦点还回去
        prev_fg_hwnd = win32gui.GetForegroundWindow()
        print(f"当前前台窗口 HWND: {prev_fg_hwnd}")
        
        print("正在强制激活微信窗口，使其获得焦点...")
        # 激活并聚焦
        win32gui.SetForegroundWindow(hwnd)
        ctrl.SetFocus()
        time.sleep(1) # 等待 1 秒给它渲染控件树
        
        print("正在获取子节点树...")
        children = ctrl.GetChildren()
        print(f"直接子节点数: {len(children)}")
        
        # 深度检索 EditControl
        edit = ctrl.EditControl(searchDepth=10)
        found = False
        if edit.Exists(maxSearchSeconds=2):
            print(f"-> [成功] 找到 Edit 控件: Name='{edit.Name}', Class='{edit.ClassName}'")
            found = True
        else:
            print("-> [失败] 未找到 Edit 控件")
            
        # 打印深度为 3 的子控件，看看出来了没有
        def walk(control, depth=0):
            if depth > 3:
                return
            indent = "  " * depth
            print(f"{indent}- [{control.ControlTypeName}] Name: '{control.Name}' | Class: '{control.ClassName}'")
            try:
                for child in control.GetChildren():
                    walk(child, depth + 1)
            except Exception:
                pass
        
        print("\n--- 控件树层级结构 (深度3) ---")
        walk(ctrl)
        
        # 把前台焦点还回去，保证不打扰用户
        if prev_fg_hwnd and prev_fg_hwnd != hwnd:
            print("正在将焦点还原给之前的窗口...")
            try:
                win32gui.SetForegroundWindow(prev_fg_hwnd)
            except Exception as e:
                print(f"还原焦点失败: {e}")
                
    except Exception as e:
        print(f"出错: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python activate_and_dump.py <HWND>")
        sys.exit(1)
    hwnd = int(sys.argv[1])
    test_activate(hwnd)
