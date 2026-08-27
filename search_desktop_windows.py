import uiautomation as auto
import re

if __name__ == "__main__":
    print("使用 UIAutomation 扫描桌面上的所有顶级窗口...")
    root = auto.GetRootControl()
    children = root.GetChildren()
    print(f"桌面顶级窗口总数: {len(children)}")
    print("-" * 75)
    
    found = 0
    for child in children:
        name = child.Name
        classname = child.ClassName
        # 匹配微信相关的名字或类名
        if re.search(r'微信|WeChat|Weixin', name, re.I) or re.search(r'WeChat|Weixin|Qt5', classname, re.I):
            found += 1
            print(f"发现匹配窗口 [{found}]:")
            print(f"  - 控件类型: {child.ControlTypeName}")
            print(f"  - 窗口名称 (Name): '{name}'")
            print(f"  - 窗口类名 (Class): '{classname}'")
            print(f"  - 句柄 (HWND): {child.NativeWindowHandle} ({hex(child.NativeWindowHandle)})")
            print(f"  - 进程 PID: {child.ProcessId}")
            print("-" * 75)
            
    if found == 0:
        print("UIAutomation 未在桌面上找到任何与微信相关的顶级窗口！")
