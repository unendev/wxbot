import uiautomation as auto
import time
import sys

# 强行重新配置 stdout 的编码为 utf-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def check_live(hwnd):
    print(f"开始 live 监听 HWND: {hwnd}")
    try:
        ctrl = auto.ControlFromHandle(hwnd)
        while True:
            # 强制广播无障碍标志
            import ctypes
            ctypes.windll.user32.SystemParametersInfoW(0x0047, True, 0, 0)
            
            msg_list = ctrl.ListControl(searchDepth=30, Name="消息")
            if msg_list.Exists(0):
                items = msg_list.GetChildren()
                print(f"\n[{time.strftime('%H:%M:%S')}] 发现消息子项数量: {len(items)}")
                for idx, item in enumerate(items[-5:]):
                    print(f"  [{idx}] Name: '{item.Name}' | Class: '{item.ClassName}'")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] 未找到消息列表")
            time.sleep(2)
    except KeyboardInterrupt:
        print("停止")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    check_live(1968418)
