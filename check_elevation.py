import win32process
import win32api
import win32con
import win32security
import psutil

def is_process_elevated(pid):
    try:
        # 打开进程句柄
        proc_handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
        # 打开进程 Token
        token_handle = win32security.OpenProcessToken(proc_handle, win32con.TOKEN_QUERY)
        # 获取提权信息 (TokenElevation)
        # TokenElevation (20) 返回一个整数，如果是 1 表示提权 (Admin)，0 表示未提权
        elevation = win32security.GetTokenInformation(token_handle, win32security.TokenElevation)
        return elevation > 0
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    print("正在检查 Weixin.exe 进程的提权 (管理员权限) 状态...")
    
    # 检查我们自己的 Python 进程
    my_pid = psutil.Process().pid
    print(f"当前 Python 进程 (PID: {my_pid}) 提权状态: {is_process_elevated(my_pid)}")
    
    # 检查所有 Weixin.exe 进程
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and proc.info['name'].lower() == 'weixin.exe':
            pid = proc.info['pid']
            elevated = is_process_elevated(pid)
            print(f"Weixin.exe 进程 (PID: {pid}) 提权状态: {elevated}")
