import uiautomation as auto
import sys

def dump_tree_by_hwnd(hwnd):
    print(f"正在绑定 HWND: {hwnd} ({hex(hwnd)})")
    try:
        ctrl = auto.ControlFromHandle(hwnd)
        print("绑定成功！开始打印控件树结构 (最大深度 4)...")
        
        def walk(control, depth=0):
            if depth > 4:
                return
            indent = "  " * depth
            # 打印类型、名称、类名
            print(f"{indent}- [{control.ControlTypeName}] Name: '{control.Name}' | Class: '{control.ClassName}'")
            try:
                for child in control.GetChildren():
                    walk(child, depth + 1)
            except Exception as e:
                print(f"{indent}  (无法获取子节点: {e})")
                
        walk(ctrl)
    except Exception as e:
        print(f"绑定或打印失败: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("请传入 HWND (十进制或十六进制)，例如:")
        print("python dump_weixin_tree.py 2690444")
        print("python dump_weixin_tree.py 0x290d8c")
        sys.exit(1)
        
    hwnd_str = sys.argv[1]
    if hwnd_str.startswith("0x"):
        hwnd = int(hwnd_str, 16)
    else:
        hwnd = int(hwnd_str)
        
    dump_tree_by_hwnd(hwnd)
