import uiautomation as auto
import sys
import psutil
import win32gui
import win32process

def get_visible_qt_windows():
    hwnds = []
    def enum_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            class_name = win32gui.GetClassName(hwnd)
            if class_name == "Qt51514QWindowIcon":
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    proc_name = psutil.Process(pid).name().lower()
                except Exception:
                    proc_name = ""
                if "weixin" in proc_name or "wechat" in proc_name:
                    hwnds.append((hwnd, pid, proc_name))
        return True
    win32gui.EnumWindows(enum_callback, None)
    return hwnds

def analyze_layout():
    print("正在通过系统 API 扫描所有可见的微信 Qt51514QWindowIcon 窗口...")
    candidates = get_visible_qt_windows()
    print(f"扫描到可见微信窗口候选: {candidates}")
    
    target_win = None
    target_hwnd = None
    
    # 逐一测试句柄，通过直接子节点数量大于 0 锁定激活了无障碍树的小号
    for hwnd, pid, proc_name in candidates:
        try:
            ctrl = auto.ControlFromHandle(hwnd)
            children = ctrl.GetChildren()
            print(f"测试 HWND: {hwnd} | PID: {pid} | 子节点数量: {len(children)}")
            if len(children) > 0:
                print(f"-> 锁定该窗口为目标小号！")
                target_win = ctrl
                target_hwnd = hwnd
                break
        except Exception as e:
            print(f"测试 HWND {hwnd} 抛出异常: {e}")
            
    if not target_win and candidates:
        print("未找到拥有子节点的窗口，退而求其次锁定第一个候选窗口...")
        target_hwnd, pid, proc_name = candidates[0]
        target_win = auto.ControlFromHandle(target_hwnd)
        
    if not target_win:
        print("未发现任何可见的微信窗口！请确保小号已显示在当前桌面上。")
        return
        
    print(f"\n【最终绑定成功】HWND={target_hwnd} ({hex(target_hwnd)}), PID={target_win.ProcessId}, Name='{target_win.Name}'")
    
    print("正在递归抓取完整的无障碍控件树...")
    lines = []
    
    def walk(control, depth=0):
        indent = "  " * depth
        info = f"{indent}- [{control.ControlTypeName}] Name: '{control.Name}' | Class: '{control.ClassName}' | HWND: {control.NativeWindowHandle}"
        lines.append(info)
        try:
            for child in control.GetChildren():
                walk(child, depth + 1)
        except Exception:
            pass
            
    walk(target_win)
    
    # 保存到文件
    with open("wx_layout_tree.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    print(f"分析完成！共抓取到 {len(lines)} 个控件。")
    print("已将完整树形结构写入 wx_layout_tree.txt")
    
    # 过滤并打印部分关键候选控件
    print("\n--- 关键候选控件筛查 ---")
    edits = []
    buttons = []
    lists = []
    for line in lines:
        if "EditControl" in line or "DocumentControl" in line:
            edits.append(line)
        if "ButtonControl" in line:
            buttons.append(line)
        if "ListControl" in line:
            lists.append(line)
            
    print(f"发现输入框类控件: {len(edits)}")
    for e in edits[:15]:
        print(f"  {e.strip()}")
    print(f"发现按钮控件: {len(buttons)}")
    for b in buttons[:15]:
        print(f"  {b.strip()}")
    print(f"发现列表控件: {len(lists)}")
    for l in lists[:15]:
        print(f"  {l.strip()}")

if __name__ == "__main__":
    analyze_layout()
