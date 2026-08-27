import uiautomation as auto
import time

def monitor():
    print("开始 15 秒实时控件树监控...")
    print("【操作指引】:")
    print("1. 脚本启动后，请在 15 秒内，将盖在小号微信上的窗口【移开】。")
    print("2. 让小号微信聊天主界面在屏幕上完全显露出来，看看控件数量是否发生变化。")
    print("3. 然后再把它遮挡回去，观察控件数量是否又变回 2 个。")
    print("-" * 70)
    
    root = auto.GetRootControl()
    
    for sec in range(1, 16):
        # 寻找微信窗口
        target_win = None
        for child in root.GetChildren():
            if child.ClassName == "Qt51514QWindowIcon":
                target_win = child
                break
                
        if not target_win:
            print(f"[{sec}s] 未找到微信窗口！")
        else:
            # 递归统计子控件数量
            nodes = []
            def collect(ctrl):
                nodes.append(ctrl)
                try:
                    for c in ctrl.GetChildren():
                        collect(c)
                except Exception:
                    pass
            collect(target_win)
            print(f"[{sec}s] 微信窗口 HWND: {target_win.NativeWindowHandle} | 控件总数: {len(nodes)}")
            
        time.sleep(1)

if __name__ == "__main__":
    monitor()
