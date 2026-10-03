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

start_bot_bat = "@echo off\r\nchcp 65001 >nul\r\nset PYTHONIOENCODING=utf-8\r\nset PYTHONUTF8=1\r\ntitle WeChat AI Bot\r\ncd /d C:\\Users\\zima\\Desktop\\wxbot\r\nuv.exe run bot.py\r\npause\r\n"

disconnect_bat = "@echo off\r\ntitle Disconnect RDP\r\nfltmc >nul 2>&1 || (\r\n    powershell -Command \"Start-Process cmd -ArgumentList '/c `\"`%~f0`\"' -Verb RunAs\"\r\n    exit /b\r\n)\r\nfor /f \"tokens=3\" %%i in ('query session ^| findstr /i \"Active\"') do (\r\n    tscon %%i /dest:console\r\n)\r\n"

# 统一写入英文名 + 中文名，并严格使用纯 ASCII / ANSI 和 Windows 标准 CRLF (\r\n) 换行
sftp.putfo(io.BytesIO(start_bot_bat.encode('ascii')), 'Desktop/start_bot.bat')
sftp.putfo(io.BytesIO(disconnect_bat.encode('ascii')), 'Desktop/disconnect_rdp.bat')

print('[+] Desktop items now:', sftp.listdir('Desktop'))
sftp.close()
client.close()

