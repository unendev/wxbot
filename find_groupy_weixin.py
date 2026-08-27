import uiautomation as auto
import sys

def search_all_depth():
    print("正在以最高深度检索模式扫描全系统 UIAutomation 树...")
    print("寻找所有 PID 为 15552 (小号) 且 ClassName 为 Qt51514QWindowIcon 的控件...")
    print("寻找所有 Weixin.exe 进程且 ClassName 为 Qt51514QWindowIcon 的控件...")
    print("-" * 80)
    
    root = auto.GetRootControl()
    found_count = 0
    
    # 递归遍历所有深度的控件
    import psutil
    def walk_search(control, depth=0):
        nonlocal found_count
        try:
            # 检查这个控件是否符合条件
            # 获取该控件对应 PID 的进程名
            pid = control.ProcessId
            try:
                proc_name = psutil.Process(pid).name().lower()
            except Exception:
                proc_name = ""
                
            if control.ClassName == "Qt51514QWindowIcon" and ("weixin" in proc_name or "wechat" in proc_name):
                found_count += 1
                print(f"发现匹配控件 [{found_count}]:")
                print(f"  - 控件类型: {control.ControlTypeName}")
                print(f"  - 名称 (Name): '{control.Name}'")
                print(f"  - 句柄 (HWND): {control.NativeWindowHandle} ({hex(control.NativeWindowHandle)})")
                print(f"  - 进程 PID: {pid} ({proc_name})")
                print(f"  - 深度 (Depth): {depth}")
                
                # 打印其子控件数
                sub_children = control.GetChildren()
                print(f"  - 直接子控件数量: {len(sub_children)}")
                for i, sc in enumerate(sub_children[:5]):
                    print(f"    - 子控件 [{i}]: 类型={sc.ControlTypeName} | 名字='{sc.Name}' | 类名='{sc.ClassName}'")
                print("-" * 80)
            
            # 继续往下递归
            for child in control.GetChildren():
                walk_search(child, depth + 1)
        except Exception:
            pass

    walk_search(root)
    print(f"检索结束，共找到 {found_count} 个匹配的控件树分支。")

if __name__ == "__main__":
    search_all_depth()
