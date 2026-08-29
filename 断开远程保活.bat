@echo off
chcp 65001 >nul
:: 自动请求管理员权限
%1 mshta vbscript:CreateObject("Shell.Application").ShellExecute("cmd.exe","/c %~s0 ::","","runas",1)(window.close)&&exit

:: 查询当前活跃的 RDP 会话 ID 并无缝切回本地控制台 (防止桌面挂起与吞键)
for /f "tokens=3" %%i in ('query session ^| findstr /i "Active"') do (
    tscon %%i /dest:console
)
