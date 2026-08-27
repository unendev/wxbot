import uiautomation as auto
import sys

def dump_tree_by_force_hwnd(hwnd):
    print(f"正在强行绑定目标句柄 HWND: {hwnd} ({hex(hwnd)})")
    try:
        ctrl = auto.ControlFromHandle(hwnd)
        print("绑定成功！开始深度扫描并保存控件树...")
        
        lines = []
        
        def walk(control, depth=0):
            if depth > 30:  # 增加深度限制
                return
            indent = "  " * depth
            info = f"{indent}- [{control.ControlTypeName}] Name: '{control.Name}' | Class: '{control.ClassName}' | HWND: {control.NativeWindowHandle}"
            lines.append(info)
            try:
                for child in control.GetChildren():
                    walk(child, depth + 1)
            except Exception:
                pass
                
        walk(ctrl)
        
        with open("wx_layout_tree.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
            
        print(f"扫描完毕！共抓取到 {len(lines)} 个控件。")
        print("已将完整树形结构写入 wx_layout_tree.txt")
        
        # 简单打印前 50 行看看
        print("\n--- 控件树前 50 行预览 ---")
        for line in lines[:50]:
            print(line)
            
    except Exception as e:
        print(f"出错: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_uia_find.py <HWND>")
        sys.exit(1)
    hwnd = int(sys.argv[1])
    dump_tree_by_force_hwnd(hwnd)
