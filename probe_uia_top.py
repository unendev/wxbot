# -*- coding: utf-8 -*-
import uiautomation as auto
import win32gui

print("=== ENUMERATING ALL UIA TOP LEVEL WINDOWS ===")
root = auto.GetRootControl()
for child in root.GetChildren():
    hwnd = child.NativeWindowHandle
    win32_title = win32gui.GetWindowText(hwnd) if hwnd else ""
    cls = win32gui.GetClassName(hwnd) if hwnd else ""
    uia_name = child.Name
    print(f"HWND: {hwnd} | Win32Title: [{win32_title}] | UIA Name: [{uia_name}] | Class: [{cls}]")
