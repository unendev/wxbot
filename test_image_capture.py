# -*- coding: utf-8 -*-
import uiautomation as auto
import time
import ctypes

def test_capture():
    print('正在寻找微信主窗口...')
    # 激活无障碍
    SPI_SETSCREENREADER = 0x0046
    ctypes.windll.user32.SystemParametersInfoW(SPI_SETSCREENREADER, 1, 0, 1)
    
    wechat_win = None
    for wnd in auto.GetRootControl().GetChildren():
        if wnd.ClassName in ['WeChatMainWndForPC', 'Qt51514QWindowIcon']:
            r = wnd.BoundingRectangle
            if r.width > 300 and r.height > 300:
                wechat_win = wnd
                break
                
    if not wechat_win:
        print('未找到微信主窗口')
        return

    msg_list = wechat_win.ListControl(Name='消息')
    if not msg_list.Exists(3, 1):
        print('未找到消息列表')
        return

    children = msg_list.GetChildren()
    print(f'找到 {len(children)} 条消息')
    
    for i, item in enumerate(children[-10:]):
        name = item.Name
        # print(f'Item {i}: name={name}')
        # 尝试看看有没有内部图片控件
        try:
            img_ctrl = item.ImageControl()
            has_img = img_ctrl.Exists(0,0)
        except:
            has_img = False

        if '图片' in name or name == '' or has_img:
            print(f'疑似图片控件！准备截图 Item {i} (name={name})...')
            try:
                # 尝试对 item 内的一个有效区域截图
                rect = item.BoundingRectangle
                if rect.width > 10 and rect.height > 10:
                    item.CaptureToImage(f'test_bubble_{i}.png')
                    print(f'成功将气泡截屏保存至 test_bubble_{i}.png')
            except Exception as e:
                print(f'气泡截图失败: {e}')
                
if __name__ == '__main__':
    test_capture()