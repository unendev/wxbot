import uiautomation as auto
import sys
import time
import win32gui
import ctypes

def force_activate_and_read(hwnd):
    print(f"目标窗口 HWND: {hwnd} ({hex(hwnd)})")
    
    # 1. 尝试使用 SendMessage 发送 WM_GETOBJECT (0x003D) 激活信号
    # Lparam = 0xFFFFFFFC (OBJID_CLIENT)
    # Wparam = 0 (表示由系统决定)
    print("正在发送 WM_GETOBJECT 消息欺骗 Qt 引擎，强制激活无障碍接口...")
    try:
        # 使用 SendMessageTimeout 避免死锁
        result = ctypes.c_longlong()
        # WM_GETOBJECT = 0x003D, OBJID_CLIENT = 0xFFFFFFFC (转换为无符号即 4294967292 或者是 -4)
        # 在 Windows 64位下，Lparam 需要是 64位无符号或有符号，-4 即可
        res = ctypes.windll.user32.SendMessageTimeoutW(
            hwnd, 
            0x003D, 
            0, 
            -4, # OBJID_CLIENT
            0x0002, # SMTO_ABORTIFHUNG
            1000, 
            ctypes.byref(result)
        )
        print(f"SendMessageTimeoutW 发送成功，返回值: {res}")
    except Exception as e:
        print(f"发送消息出错: {e}")
        
    print("等待 1.5 秒让 Qt 控件树动态加载...")
    time.sleep(1.5)
    
    # 2. 绑定窗口并查询
    try:
        ctrl = auto.ControlFromHandle(hwnd)
        print("绑定窗口成功！")
        
        # 获取第一层直接子节点
        children = ctrl.GetChildren()
        print(f"直接子节点数量: {len(children)}")
        for idx, child in enumerate(children):
            print(f"  [{idx}] Type: {child.ControlTypeName} | Name: '{child.Name}' | Class: '{child.ClassName}'")
            
        # 尝试深度搜索 Edit 控件
        print("正在深度搜索 Edit 控件...")
        edit = ctrl.EditControl(searchDepth=10)
        if edit.Exists(maxSearchSeconds=3):
            print(f"-> [大成功!!!] 成功找到输入框: Name='{edit.Name}', Class='{edit.ClassName}'")
        else:
            print("-> [失败] 依然没有找到 EditControl")
            
        doc = ctrl.DocumentControl(searchDepth=10)
        if doc.Exists(maxSearchSeconds=1):
            print(f"-> [大成功!!!] 成功找到文档输入框: Name='{doc.Name}', Class='{doc.ClassName}'")
            
    except Exception as e:
        print(f"获取树出错: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_wm_getobject.py <HWND>")
        sys.exit(1)
    hwnd = int(sys.argv[1])
    force_activate_and_read(hwnd)
