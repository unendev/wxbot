import os
import re
import sys
import time
from io import BytesIO
import requests
import psutil
import uiautomation as auto
import win32gui
import win32process
import win32clipboard
import win32api
import win32con
from PIL import Image
import winreg
import subprocess
import ctypes

# 强行重新配置 stdout 的编码为 utf-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 强制把工作目录切换到 bot.py 脚本所在的绝对目录，防止相对路径权限报错
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"[+] 已强制校准工作目录至: {script_dir}")
except Exception as e:
    print(f"[-] 强制校准工作目录失败: {e}")

# 日志持久化双写 Logger 逻辑，方便远程 SSH 直接查阅实时日志
class Logger(object):
    def __init__(self, filename="bot.log"):
        self.terminal = sys.stdout
        self.log_path = filename

    def write(self, message):
        self.terminal.write(message)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(message)
        except Exception:
            pass

    def flush(self):
        self.terminal.flush()

sys.stdout = Logger("bot.log")

# LLM 配置 (使用用户提供的参数)
LLM_API_URL = "http://127.0.0.1:7860/v1/chat/completions"
LLM_API_KEY = "123456"
LLM_MODEL = "gemini-3-flash-preview"

# 微信 4.0 配置
TARGET_GROUP = "大丑"
ROBOT_NAME = "小丑"


class SimpleBrain:
    """根据麦麦 (MaiBot) 哲学设计的类人对话大脑"""

    def __init__(self):
        self.system_prompt = f"""
你正在微信群“{TARGET_GROUP}”里和群友闲聊。你的群名片是“{ROBOT_NAME}”。
你的定位是：活跃在群聊里的真实人类生命体（性格可参考接地气、爱上网冲浪的大二学生），绝对不是一个回答问题的“AI 助手”。
你的核心发言原则是“最像真人，而不是做好人”。你不追求完美和高效，但追求亲切和真实。

【极致口语规约 - 坚决消灭 GPT 腔】：
1. 坚决禁止长篇大论！发言必须极其简短、言简意赅，10-20 个字内最佳，绝对不准超过 30 个字。
2. 坚决禁止分点作答！绝对不要输出诸如“1. ... 2. ...”或者带各类粗体 Markdown 格式的分点排版。
3. 参考贴吧、微博、知乎里真实群友的闲聊接梗风格：白话、平淡、带点小幽默或一针见血的吐槽。
4. 可以适当且仅使用微信内置表情字符表达情绪（例如 [翻白眼], [流汗], [苦涩], [旺柴], [呲牙], [抠鼻], [微笑]），绝对不输出 Emoji。
5. 顺着话题自然接茬即可，不要总是复述或提及你被 @ 的身份。
6. 如果群友要你发图/发表情包，或者你觉得极其无语、极其适合发图配合你吐槽时，你可以在回复中附加 `[send_image: scratch/test_meme.png]`。非必要请不要乱发。
"""

    def think(self, user_msg, history=[]):
        try:
            messages = [{"role": "system", "content": self.system_prompt}]
            # 携带最近 30 次的历史记录，让机器人拥有更长久的上下文记忆
            for h in history[-30:]:
                messages.append({"role": "user", "content": h})

            messages.append({"role": "user", "content": user_msg})

            payload = {"model": LLM_MODEL, "messages": messages, "temperature": 0.8}
            headers = {
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                LLM_API_URL, headers=headers, json=payload, timeout=20
            )
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                # 过滤掉回复中可能存在的 "小丑：" 前缀
                content = re.sub(f"^{ROBOT_NAME}[:：]\s*", "", content)
                return content
            else:
                return f"[小丑自动应答] (本地LLM返回HTTP {response.status_code}) 收到！你刚才说的是：'{user_msg}'"
        except Exception as e:
            # 当本地推理服务离线时，降级为回声测试，以便独立验证静默发送通道
            return f"[小丑自动应答] (本地LLM离线，已激活回声测试) 收到！你刚才对我说：'{user_msg}'"


brain = SimpleBrain()


def ensure_test_meme():
    """在本地生成一张用于测试发图的蓝底白字搞笑表情包"""
    os.makedirs("scratch", exist_ok=True)
    image_path = "scratch/test_meme.png"
    try:
        img = Image.new("RGB", (400, 120), color=(100, 149, 237))
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        d.text((10, 40), "No Words, Just Slapped you with a meme!\n(WeChat Bot Test Meme)", fill=(255, 255, 255))
        img.save(image_path, "PNG")
        print(f"[+] 搞笑测试表情包已生成在: {image_path}")
    except Exception as e:
        print(f"[-] 生成测试表情包失败: {e}")


def find_wechat_executable():
    """从 Windows 注册表中自动查找微信的安装绝对路径"""
    paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\WeChat",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\WeChat",
        r"SOFTWARE\Tencent\WeChat"
    ]
    for path in paths:
        for root in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
            try:
                key = winreg.OpenKey(root, path)
                try:
                    install_path, _ = winreg.QueryValueEx(key, "InstallPath")
                    exe_path = os.path.join(install_path, "WeChat.exe")
                    if os.path.exists(exe_path):
                        return exe_path
                except Exception:
                    pass
            except Exception:
                pass
    default_path = r"C:\Program Files\Tencent\WeChat\WeChat.exe"
    if os.path.exists(default_path):
        return default_path
    return None


def get_wechat_hwnds():
    """使用 Windows API 扫描所有可见的微信 4.0 窗口句柄"""
    hwnds = []

    def enum_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            class_name = win32gui.GetClassName(hwnd)
            # 微信 4.0 顶级窗口类名是 Qt51514QWindowIcon
            if class_name == "Qt51514QWindowIcon":
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    proc_name = psutil.Process(pid).name().lower()
                except Exception:
                    proc_name = ""
                if "weixin" in proc_name or "wechat" in proc_name:
                    hwnds.append(hwnd)
        return True

    win32gui.EnumWindows(enum_callback, None)
    return hwnds


def find_child_by_name(control, name_keyword, max_depth=15):
    """递归搜索后代控件，匹配 Name 关键字 (避开左侧会话列表项，锁定右侧聊天标题)"""
    if max_depth <= 0:
        return None
    try:
        # 避开左侧会话列表项，防止误判为已点开此会话
        if control.ClassName == "mmui::ChatSessionCell":
            return None
            
        name = control.Name
        if name and name_keyword in name:
            return control
    except Exception:
        pass

    try:
        for child in control.GetChildren():
            res = find_child_by_name(child, name_keyword, max_depth - 1)
            if res:
                return res
    except Exception:
        pass
    return None


def switch_to_group(wechat_ctrl, target_group_name):
    """
    如果在右侧聊天详情里没有匹配到群，尝试在左侧会话列表中找到目标群并静默点击切换过去
    """
    try:
        # 微信4.0的会话列表深度在22层左右
        session_list = wechat_ctrl.ListControl(searchDepth=25, Name="会话")
        if session_list.Exists(0):
            for item in session_list.GetChildren():
                if item.ClassName == "mmui::ChatSessionCell" and target_group_name in item.Name:
                    clean_item_name = item.Name.replace('\n', ' ')
                    print(f"[+] 发现左侧会话列表中有目标群聊: '{clean_item_name}'，触发静默双击切换...")
                    # 模拟点击切换会话
                    item.Click(simulateClick=True)
                    time.sleep(0.8)
                    return True
    except Exception as e:
        print(f"[-] 自动切换会话失败: {e}")
    return False

def bind_wechat_bot(target_group_name):
    """
    遍历微信窗口句柄，精准绑定当前打开了目标群聊界面的那台微信实例 (即机器人小号)
    """
    hwnds = get_wechat_hwnds()
    if not hwnds:
        print(
            "[-] 未发现运行中且可见的微信 4.0 窗口！请确保小号主界面未最小化且已呼出。"
        )
        return None, None

    print(f"[*] 发现 {len(hwnds)} 个候选微信窗口，正在进行群聊特征匹配...")
    for hwnd in hwnds:
        try:
            ctrl = auto.ControlFromHandle(hwnd)
            # 1. 尝试直接匹配已打开的群名
            matched_ctrl = find_child_by_name(ctrl, target_group_name, max_depth=35)
            if matched_ctrl:
                print(
                    f"[+] 匹配成功！在 HWND {hwnd} ({hex(hwnd)}) 下发现目标群聊特征: '{matched_ctrl.Name}'"
                )
                return ctrl, hwnd
                
            # 2. 如果没找到，尝试在左侧会话列表中静默切换到该会话
            print(f"[*] 未在 HWND {hwnd} 直观看到群标题，正在尝试静默路由切入 '{target_group_name}' 聊天...")
            if switch_to_group(ctrl, target_group_name):
                # 切换后，重新匹配群标题以确认锁定
                matched_ctrl = find_child_by_name(ctrl, target_group_name, max_depth=35)
                if matched_ctrl:
                    print(f"[+] 自动切换并匹配成功！在 HWND {hwnd} ({hex(hwnd)}) 下锁定特征: '{matched_ctrl.Name}'")
                    return ctrl, hwnd
        except Exception as e:
            continue

    print(f"[-] 未能在任何微信窗口中找到正在打开的群聊 '{target_group_name}' 界面！")
    print("    请确保小号微信已经点开了该群聊，使其正处于聊天会话界面。")
    return None, None


def backup_clipboard():
    """备份当前剪贴板中的所有可用格式及数据"""
    backup = {}
    try:
        win32clipboard.OpenClipboard()
        fmt = win32clipboard.EnumClipboardFormats(0)
        while fmt:
            try:
                data = win32clipboard.GetClipboardData(fmt)
                backup[fmt] = data
            except Exception:
                pass
            fmt = win32clipboard.EnumClipboardFormats(fmt)
    except Exception as e:
        print(f"[-] 备份剪贴板失败: {e}")
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass
    return backup


def restore_clipboard(backup):
    """将备份的格式和数据恢复回剪贴板"""
    if not backup:
        return
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        for fmt, data in backup.items():
            try:
                win32clipboard.SetClipboardData(fmt, data)
            except Exception:
                pass
    except Exception as e:
        print(f"[-] 还原剪贴板失败: {e}")
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


def send_image_silently(wechat_ctrl, image_path):
    """
    静默粘贴并发送本地图片
    """
    if not os.path.exists(image_path):
        print(f"[-] 图片路径不存在: {image_path}")
        return False
        
    try:
        # 1. 打开图片并转换为 CF_DIB 格式所需的数据 (去掉 14 字节的 BMP 文件头)
        img = Image.open(image_path)
        output = BytesIO()
        img.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()
        
        # 2. 备份当前系统剪贴板
        clip_backup = backup_clipboard()
        
        try:
            # 3. 写入图片到剪贴板
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            
            # 4. 定位输入框
            edit = wechat_ctrl.EditControl(searchDepth=35, ClassName="mmui::ChatInputField")
            if not edit.Exists(0):
                return False
                
            # 5. 聚焦输入框并粘贴
            edit.SetFocus()
            time.sleep(0.1)
            edit.SendKeys("{Ctrl}v")
            time.sleep(0.3)
            
            # 6. UIA 回车与物理回车双保底发送
            edit.SendKeys("{Enter}")
            time.sleep(0.2)
            win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
            win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.3)
        finally:
            # 7. 还原系统剪贴板
            restore_clipboard(clip_backup)
            
        return True
    except Exception as e:
        print(f"[-] 静默发送图片失败: {e}")
        return False


def send_message_silently(wechat_ctrl, text):
    """
    静默发送消息：直接通过 UIA 内存注入文本并发送回车键，不占用鼠标和剪贴板。
    """
    try:
        # 1. 定位输入框 (mmui::ChatInputField)
        edit = wechat_ctrl.EditControl(searchDepth=35, ClassName="mmui::ChatInputField")
        if not edit.Exists(0):
            print("[-] 未找到输入框，请确保聊天窗口处于激活/可见状态")
            return False

        # 2. 注入文本 (使用 ValuePattern 绕过剪贴板)
        edit.GetValuePattern().SetValue(text)
        time.sleep(0.2)

        # 3. 直接向输入框投递回车键，秒发消息
        print("[*] 正在向输入框静默发送回车键...")
        edit.SendKeys("{Enter}")
        time.sleep(0.2)

        # 4. 校验发送状态：微信发送成功后，输入框文本会自动清空
        val = edit.GetValuePattern().Value
        if not val or len(val.strip()) == 0:
            return True
        else:
            print("[-] 回车键投递后输入框未清空，尝试重发一次...")
            edit.SendKeys("{Enter}")
            time.sleep(0.2)
            val = edit.GetValuePattern().Value
            return not val or len(val.strip()) == 0

    except Exception as e:
        print(f"[-] 发送消息失败: {e}")
        return False


def get_latest_messages(wechat_ctrl):
    """获取当前聊天窗口中最新的几条消息文本"""
    messages = []
    try:
        # 定位聊天消息的 List 容器 (mmui::RecyclerListView)
        # 微信4.0的聊天消息列表深度很深 (通常在22层以上)，因此 searchDepth 设为 30
        msg_list_ctrl = wechat_ctrl.ListControl(searchDepth=30, Name="消息")
        if not msg_list_ctrl.Exists(maxSearchSeconds=1):
            return messages

        # 遍历消息列表下的每一条 ListItemControl (mmui::ChatTextItemView 等)
        items = msg_list_ctrl.GetChildren()
        for item in items:
            name = item.Name
            if name:
                messages.append(name)
    except Exception as e:
        print(f"[-] 获取消息列表出错: {e}")
    return messages


def start_listening(target_group_name):
    print("[*] 微信群聊静默监听机器人正在启动...")
    
    # 自动编译测试表情包图片
    ensure_test_meme()

    # 强制开启全局屏幕阅读器标志，激活微信 Qt 渲染树
    import ctypes

    print("[*] 正在向系统广播开启无障碍 (Screen Reader) 标志...")
    ctypes.windll.user32.SystemParametersInfoW(0x0047, True, 0, 0)

    wechat_ctrl, hwnd = bind_wechat_bot(target_group_name)

    if not wechat_ctrl:
        print("[-] 启动失败。")
        return

    print(f"[+] 机器人已成功绑定小号微信窗口 HWND: {hwnd} ({hex(hwnd)})")
    print(f"[*] 监听目标群聊: {target_group_name}")
    print("[*] 机器人小号昵称: " + ROBOT_NAME)
    print("[*] 正在加载历史聊天记录预览...")

    # 获取当前历史记录
    history = get_latest_messages(wechat_ctrl)
    print("-" * 50)
    for msg in history[-10:]:
        print(f"[历史消息] {msg}")
    print("-" * 50)
    print("[*] 开始后台实时静默监听新消息 (每 1 秒刷新一次)...")

    last_msg_list = history
    last_sent_reply = ""
    
    try:
        while True:
            time.sleep(1)
            
            # 24H 微信异常掉线/崩溃自愈逻辑
            if not win32gui.IsWindow(hwnd):
                print("[-] 检测到微信窗口已关闭或崩溃！启动 24H 自动守护自愈逻辑...")
                wechat_exe = find_wechat_executable()
                if wechat_exe:
                    print(f"[*] 正在重新拉起微信客户端: {wechat_exe}")
                    try:
                        subprocess.Popen(wechat_exe)
                    except Exception as err:
                        print(f"[-] 重新拉起微信失败: {err}")
                
                # 循环等待微信登录并重新激活主窗口
                while True:
                    time.sleep(5)
                    print("[*] 正在等待微信主窗口重新打开并登录...")
                    # 重新向系统广播开启无障碍 (Screen Reader) 标志
                    ctypes.windll.user32.SystemParametersInfoW(0x0047, True, 0, 0)
                    
                    new_ctrl, new_hwnd = bind_wechat_bot(target_group_name)
                    if new_ctrl:
                        wechat_ctrl = new_ctrl
                        hwnd = new_hwnd
                        last_msg_list = get_latest_messages(wechat_ctrl)
                        print("[+] 微信已重新绑定成功，自愈恢复正常监听。")
                        break
                continue

            current_msgs = get_latest_messages(wechat_ctrl)
            if not current_msgs:
                continue

            # 对比获取新消息
            if len(current_msgs) > len(last_msg_list):
                new_count = len(current_msgs) - len(last_msg_list)
                new_msgs = current_msgs[-new_count:]
                for msg in new_msgs:
                    print(f"[监听到新消息] {msg}")
                    
                    # 避免自己回复自己 (套娃过滤)
                    if last_sent_reply and (last_sent_reply in msg or msg in last_sent_reply):
                        print(f"  [*] 过滤机器人自身的回复，跳过。")
                        continue

                    # 更加宽松的匹配：只要包含机器人名字或被认为是@消息
                    is_at_me = ROBOT_NAME in msg or "@机器人" in msg or "\u2005" in msg
                    if is_at_me:
                        print(f"  ⚡ 匹配到 @机器人 信号! (匹配内容: {msg})")

                        # 提取内容：去掉 @小丑 及其后的空格/零宽空格
                        clean_msg = re.sub(
                            f"@.*?({ROBOT_NAME}|机器人)[\u2005\s]*", "", msg
                        )
                        print(f"  [*] 提取到的纯内容: {clean_msg}")
                        clean_msg = re.sub(
                            f"@{ROBOT_NAME}\u2005|@{ROBOT_NAME}\s*", "", msg
                        )

                        # 调用 LLM 思考
                        print(f"  [*] 正在思考回复...")
                        reply_content = brain.think(clean_msg, history=last_msg_list)

                        # 解析发图指令并静默发送
                        image_match = re.search(r"\[send_image:\s*([^\]]+)\]", reply_content)
                        sent_any = False
                        if image_match:
                            image_path = image_match.group(1).strip()
                            print(f"  [*] 检测到发图指令，正在静默发送图片: {image_path}")
                            if send_image_silently(wechat_ctrl, image_path):
                                sent_any = True
                            reply_content = re.sub(r"\[send_image:\s*[^\]]+\]", "", reply_content).strip()

                        # 发送文本回复
                        if reply_content:
                            if send_message_silently(wechat_ctrl, reply_content):
                                print(f"  [√] 已回复文本: {reply_content}")
                                last_sent_reply = reply_content
                                sent_any = True
                            else:
                                print(f"  [X] 文本回复发送失败")
                        else:
                            if sent_any:
                                last_sent_reply = "[图片]"

            elif (
                len(current_msgs) == len(last_msg_list)
                and current_msgs
                and current_msgs[-1] != last_msg_list[-1]
            ):
                # 即使长度相同，如果最后一条变了也视作有新消息（例如被撤回或快速连发替换）
                msg = current_msgs[-1]
                
                # 避免自己回复自己 (套娃过滤)
                if last_sent_reply and (last_sent_reply in msg or msg in last_sent_reply):
                    last_msg_list = current_msgs
                    continue
                    
                print(f"[收到最新替换消息] {msg}")
                if ROBOT_NAME in msg or "@机器人" in msg:
                    print(f"  ⚡ 触发 @机器人 消息！ 消息内容: {msg}")

                    # 提取纯内容
                    clean_msg = re.sub(f"@{ROBOT_NAME}\u2005|@{ROBOT_NAME}\s*", "", msg)

                    # 调用 LLM 思考
                    print(f"  [*] 正在思考回复...")
                    reply_content = brain.think(clean_msg, history=last_msg_list)

                    # 解析发图指令并静默发送
                    image_match = re.search(r"\[send_image:\s*([^\]]+)\]", reply_content)
                    sent_any = False
                    if image_match:
                        image_path = image_match.group(1).strip()
                        print(f"  [*] 检测到发图指令，正在静默发送图片: {image_path}")
                        if send_image_silently(wechat_ctrl, image_path):
                            sent_any = True
                        reply_content = re.sub(r"\[send_image:\s*[^\]]+\]", "", reply_content).strip()

                    # 发送文本回复
                    if reply_content:
                        if send_message_silently(wechat_ctrl, reply_content):
                            print(f"  [√] 已回复文本: {reply_content}")
                            last_sent_reply = reply_content
                            sent_any = True
                        else:
                            print(f"  [X] 文本回复发送失败")
                    else:
                        if sent_any:
                            last_sent_reply = "[图片]"

            last_msg_list = current_msgs

    except KeyboardInterrupt:
        print("\n[*] 机器人已停止监听。")


if __name__ == "__main__":
    start_listening(TARGET_GROUP)
