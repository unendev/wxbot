# -*- coding: utf-8 -*-
import io
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.50.109', port=22, username='zima', password='131232111', timeout=10)
sftp = client.open_sftp()

for item in sftp.listdir('Desktop'):
    if item.endswith('.bat'):
        try:
            sftp.remove('Desktop/' + item)
            print('[*] Removed old bat:', item)
        except Exception as e:
            print('[-] Error removing:', item, e)

start_bot_bat = """@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "C:\\Users\\zima\\Desktop\\wxbot"
title WeChat AI Bot (Zimaboard)
echo ============================================================
echo   微信 AI 助手 (Zimaboard 原生运行环境)
echo ============================================================
echo [*] 正在启动机器人...
uv.exe run bot.py
pause
"""

disconnect_bat = """@echo off
fltmc >nul 2>&1 || (
    powershell -Command "Start-Process cmd -ArgumentList '/c `\"`%~f0`\"' -Verb RunAs"
    exit /b
)

for /f "tokens=3" %%i in ('query session ^| findstr /i "Active"') do (
    tscon %%i /dest:console
)
"""

sftp.putfo(io.BytesIO(start_bot_bat.encode('gbk')), 'Desktop/启动微信AI.bat')
sftp.putfo(io.BytesIO(disconnect_bat.encode('gbk')), 'Desktop/断开远程桌面(防黑屏).bat')

print('[+] Desktop items now:', sftp.listdir('Desktop'))
sftp.close()
client.close()

