import uiautomation as auto
import time

def find_active_wechat_window():
    # 查找类名为 Qt51514QWindowIcon 的窗口
    root = auto.GetRootControl()
    for child in root.GetChildren():
        if child.ClassName == "Qt51514QWindowIcon":
            # 检查是否可见，并且进程名确实是 Weixin.exe
            # 虽然我们前面验证了，这里我们可以先不管进程名，只要类名匹配就行
            # 我们打印出来它的 HWND 和名称
            print(f"找到 Qt 微信窗口: HWND={child.NativeWindowHandle} ({hex(child.NativeWindowHandle)}), Name='{child.Name}'")
            # 统计子控件数量
            children_list = []
            def collect(ctrl):
                children_list.append(ctrl)
                try:
                    for c in ctrl.GetChildren():
                        collect(c)
                except Exception:
                    pass
            collect(child)
            print(f"  - 控件总数 (包含自身): {len(children_list)}")
            if len(children_list) > 1:
                print("  - [成功] 已成功读取到微信子控件树！")
                # 打印前 10 个控件的信息作为预览
                print("  - 控件前 15 个预览:")
                for i, c in enumerate(children_list[:15]):
                    print(f"    [{i}] 类型: {c.ControlTypeName} | 名字: '{c.Name}' | 类名: '{c.ClassName}'")
                return child
            else:
                print("  - [失败] 控件树为空，这通常是因为窗口在其他虚拟桌面、最小化或被挂起。")
    return None

if __name__ == "__main__":
    print("开始检测可见微信窗口的 UIAutomation 树...")
    print("提示: 请确保微信窗口在【当前虚拟桌面】下打开（可以被其他窗口完全盖住遮挡，但不能最小化，也不能在其他虚拟桌面）。")
    print("-" * 70)
    find_active_wechat_window()
