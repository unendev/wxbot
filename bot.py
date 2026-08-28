# -*- coding: utf-8 -*-
"""
微信 AI 百科全书智能助手 (精准图文伴随装箱 + 30轮多模态记忆闭环)
"""
import time
import sys
import os
import re
import base64
import ctypes
from pathlib import Path
import requests
import uiautomation as auto
import win32con
import win32gui

# 1. 控制台编码
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 2. 读取配置
LLM_API_URL = os.getenv("LLM_API_URL", "http://127.0.0.1:7860/v1/chat/completions")
LLM_API_KEY = os.getenv("LLM_API_KEY", "123456")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

SYSTEM_PROMPT = """请回答用户的问题。
【排版要求】：
1. 严禁使用任何 Markdown 格式符号（严禁使用 ** 加粗、# 标题、* 列表、--- 分割线）；
2. 请使用标准换行、空行或数字序号进行纯文本排版。
"""

def clean_markdown_to_text(text: str) -> str:
    """过滤 Markdown 标记，转为微信最佳纯文本"""
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    t = re.sub(r"\*([^*]+)\*", r"\1", text)
    t = re.sub(r"__([^_]+)__", r"\1", text)
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"^-{3,}\s*$", "", t, flags=re.MULTILINE)
    return t.strip()

# 3. 激活无障碍
SPI_SETSCREENREADER = 0x0046
ctypes.windll.user32.SystemParametersInfoW(SPI_SETSCREENREADER, 1, 0, 1)

print("=" * 55)
print(f" 微信 AI 百科全书机器人已启动 (模型: {LLM_MODEL})")
print("=" * 55)

# 4. 全能定位微信窗口
found_hwnd = None
def enum_cb(hwnd, _):
    global found_hwnd
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        if "WeChat" in cls or "Qt" in cls or "微信" in title:
            rect = win32gui.GetWindowRect(hwnd)
            if (rect[2] - rect[0]) > 300 and (rect[3] - rect[1]) > 300:
                found_hwnd = hwnd
                return False
    return True

try:
    win32gui.EnumWindows(enum_cb, None)
except Exception:
    pass

if not found_hwnd:
    print("[-] 未找到微信窗口，请确保微信已在桌面上显示！")
    sys.exit(1)

print(f"[+] 成功锁定微信窗口 (HWND: {found_hwnd})")
wechat_win = auto.ControlFromHandle(found_hwnd)

# 5. 定位消息列表
msg_list = None
wnd_rect = wechat_win.BoundingRectangle
for child in wechat_win.GetChildren():
    if child.ControlTypeName == "ListControl" and child.BoundingRectangle.left > (wnd_rect.left + 150):
        msg_list = child
        break

if not msg_list:
    msg_list = wechat_win.ListControl(searchDepth=25)

print("[+] 成功挂载聊天消息流！")

# 6. 微信图片存储目录探测 (微信 4.0 将落盘移至 MsgAttach 或 Image)
WECHAT_BASE_DIR = Path(os.environ.get("USERPROFILE", "C:/Users/a1634")) / "Documents" / "WeChat Files" / "wxid_zixek3hhdfdv22" / "FileStorage"

def find_latest_image(max_age_seconds: float = 60.0) -> Path:
    """自动获取微信最近接收并解密的图片文件"""
    if not WECHAT_BASE_DIR.exists():
        return None
    try:
        now = time.time()
        latest_file = None
        latest_mtime = 0
        search_dirs = [WECHAT_BASE_DIR / "Image", WECHAT_BASE_DIR / "MsgAttach"]
        for d in search_dirs:
            if not d.exists():
                continue
            for ext in ["*.jpg", "*.png", "*.jpeg"]:
                for f in d.rglob(ext):
                    try:
                        mtime = f.stat().st_mtime
                        if (now - mtime) <= max_age_seconds and mtime > latest_mtime:
                            latest_mtime = mtime
                            latest_file = f
                    except Exception:
                        pass
        return latest_file
    except Exception:
        return None

# 7. 多轮对话上下文记忆 (保留最近 30 轮深度记忆，超 30 分钟自然重置)
MAX_HISTORY_TURNS = 30
history_messages = []
last_active_time = time.time()

def call_llm(question: str, image_path: Path = None) -> str:
    """调用本地 Gemini 生成回答 (支持纯文本与原生视觉看图)"""
    global history_messages, last_active_time
    
    # 超过 30 分钟未说话，自动重置对话
    if time.time() - last_active_time > 1800:
        history_messages.clear()
        print("[*] 距离上次对话已超 30 分钟，自动开启全新对话主题。")
        
    last_active_time = time.time()
    
    # 组装用户输入内容 (纯文本 or 图文多模态)
    if image_path and image_path.exists():
        print(f"[*] 正在为 Gemini 视觉大脑编码图片: {image_path.name}")
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        user_content = [
            {"type": "text", "text": question or "请仔细分析这张图片的内容并给出详细专业的解答。"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}}
        ]
    else:
        user_content = question
    
    # 将内容永久装入 30 轮记忆箱子
    history_messages.append({"role": "user", "content": user_content})
    
    if len(history_messages) > MAX_HISTORY_TURNS * 2:
        history_messages = history_messages[-MAX_HISTORY_TURNS * 2:]
        
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history_messages,
        "temperature": 0.7
    }
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    start_t = time.time()
    try:
        resp = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=30)
        cost = time.time() - start_t
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            clean_content = clean_markdown_to_text(content)
            # 记录助手的回复到历史记忆中 (存纯文本)
            history_messages.append({"role": "assistant", "content": clean_content})
            print(f"[+] 大模型生成成功 (耗时: {cost:.2f}s, 当前记忆轮数: {len(history_messages)//2}/{MAX_HISTORY_TURNS})")
            return clean_content
        else:
            print(f"[-] 大模型返回错误 HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        cost = time.time() - start_t
        print(f"[-] 请求大模型异常 (耗时: {cost:.2f}s): {e}")
    return ""

def send_reply(reply_text: str):
    """向微信输入框写入并发送"""
    try:
        win32gui.SetForegroundWindow(found_hwnd)
        time.sleep(0.05)
        
        input_box = wechat_win.EditControl(searchDepth=35)
        if not input_box.Exists(0.3):
            input_box = wechat_win.EditControl(searchDepth=20)
            
        val_pattern = input_box.GetValuePattern()
        if val_pattern:
            val_pattern.SetValue(reply_text)
        else:
            input_box.SendKeys(reply_text)
            
        time.sleep(0.05)
        input_box.Click(simulateMove=False)
        time.sleep(0.05)
        auto.SendKeys("{Enter}")
        return True
    except Exception as e:
        print(f"[-] 发送异常: {e}")
        return False

# 【修复一：序列重叠匹配状态机 (Sequence Overlap Matching)】
# 彻底废弃所有带坐标、宽高的 processed_item_keys，不再惧怕任何滚屏！
prev_msg_list = []

def parse_current_messages(children, mid_x):
    """将屏幕上的控件列表解析为 (text, is_self, item_obj) 的纯净数组"""
    parsed = []
    for item in children:
        text = item.Name.strip() if item.Name else ""
        
        # 过滤系统噪点
        if text in ["头像", "按钮", "滚动条", "返回"] or text.endswith("撤回了一条消息"):
            continue
            
        if not text:
            # 探测纯图片
            try:
                if item.ImageControl().Exists(0, 0):
                    text = "[图片]"
                else:
                    continue
            except:
                continue
                
        is_self = False
        r = item.BoundingRectangle
        sub_children = item.GetChildren()
        if sub_children:
            last_sub = sub_children[-1]
            if last_sub.BoundingRectangle.left > mid_x:
                is_self = True
        else:
            if r.left > mid_x:
                is_self = True
                
        parsed.append((text, is_self, item))
    return parsed

print("[*] 正在同步当前屏幕历史基线，请等待 1.5 秒...")
time.sleep(1.5)
children = msg_list.GetChildren()
if children:
    list_rect = msg_list.BoundingRectangle
    list_mid_x = (list_rect.left + list_rect.right) / 2
    prev_msg_list = parse_current_messages(children, list_mid_x)
    print(f"[+] 冷启动已建立绝对静默防波堤 (成功锁定末端 {len(prev_msg_list)} 条序列指纹)")

print("[*] 正在实时监听中... (请在微信里发送图片或问题测试)")
print("-" * 55)

# 主工作循环
try:
    while True:
        children = msg_list.GetChildren()
        if children:
            list_rect = msg_list.BoundingRectangle
            list_mid_x = (list_rect.left + list_rect.right) / 2
            
            curr_msg_list = parse_current_messages(children, list_mid_x)
            
            # 【修复二：数学级后缀重叠匹配 (寻找最大重叠 K)】
            overlap_k = 0
            # 提取比对指纹：只用 (text, is_self) 做比对，不管对象是否销毁重建
            prev_fingerprints = [(t, s) for t, s, _ in prev_msg_list]
            curr_fingerprints = [(t, s) for t, s, _ in curr_msg_list]
            
            max_possible_k = min(len(prev_fingerprints), len(curr_fingerprints))
            for k in range(max_possible_k, 0, -1):
                if prev_fingerprints[-k:] == curr_fingerprints[:k]:
                    overlap_k = k
                    break
            
            # 提取新增的项
            new_items = curr_msg_list[overlap_k:]
            
            # 刷新历史游标 (哪怕没有新消息，也要时刻同步最新的屏幕状态，以防滚动)
            if curr_msg_list:
                prev_msg_list = curr_msg_list
                
            if new_items:
                incoming_texts = []
                recent_img = None
                
                now_str = time.strftime("%H:%M:%S")
                
                for text, is_self, item_obj in new_items:
                    # 我们只处理对方发来的消息 (is_self=False)
                    if is_self:
                        continue
                        
                    incoming_texts.append(text)
                    
                    # 【修复三：神级解密法 —— 闪击大图触发落盘，然后 ESC 退闪】
                    if text == "[图片]" or text == "图片":
                        print(f"[{now_str}] 发现对方发来图片，正在闪电执行：点开 -> 解密落盘 -> 闪退大图...")
                        try:
                            # 模拟点击该气泡，强制微信调出图片查看器并落盘解密 .dat
                            item_obj.Click(simulateMove=False)
                            # 等待微信反应、打开窗口并写硬盘
                            time.sleep(0.8)
                            # 盲发 ESC 关闭图片查看器
                            auto.SendKeys("{ESC}")
                            time.sleep(0.2)
                            
                            # 立即去缓存池里捞刚解密的高清原图
                            found_img = find_latest_image(max_age_seconds=15.0)
                            if found_img:
                                recent_img = found_img
                                print(f"[+] 绝杀微信图片加密：已成功从本地提取高清原图 {recent_img.name}")
                            else:
                                print("[-] 闪电解密动作完成，但在硬盘未寻获新图片")
                        except Exception as e:
                            print(f"[-] 图片闪电解密动作失败: {e}")
                
                # 触发大模型请求
                if incoming_texts:
                    print(f"\n[{now_str}] 捕获到对方新消息: {' | '.join(incoming_texts)}")
                    
                    # 提取纯文本提问
                    pure_texts = [m for m in incoming_texts if m not in ["[图片]", "图片"]]
                    question_text = "\n".join(pure_texts) if pure_texts else "请仔细分析这张图片的内容并给出详细专业的解答。"
                    
                    if recent_img:
                        print(f"[+] 正在将刚截获的高清原图装箱送入记忆: {recent_img.name}")
                    
                    print("[*] 正在请求大模型生成解答 (已携带完整图文上下文)...")
                    reply = call_llm(question_text, image_path=recent_img)
                    
                    if reply:
                        print("[*] 正在自动发送到微信输入框...")
                        send_reply(reply)
                        print(f"[{now_str}] [√] 回复已成功发出！")
                    else:
                        print("[-] 未能获取有效回复，跳过本次发送")
                    
        time.sleep(0.6)
except KeyboardInterrupt:
    print("\n[*] 机器人已安全退出。")
