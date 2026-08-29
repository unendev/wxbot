# -*- coding: utf-8 -*-
"""
Steam 创意工坊 MOD 自动监控与微信战报推送服务
MOD ID: 3555025039 (task board)
特性：
1. 5 分钟 (300s) 定时高精度轮询 Steam 官方 Web API
2. 增量 Diff 检测：订阅/收藏/浏览量增长时即刻生成战报并推送至微信
3. 状态文件本地持久化 (steam_mod_cache.json)
"""
import os
import sys
import time
import json
import logging
from pathlib import Path
import requests

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SteamMonitor] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("SteamMonitor")

WORKSHOP_ID = int(os.getenv("STEAM_MOD_ID", "3555025039"))
POLL_INTERVAL_SECONDS = int(os.getenv("STEAM_POLL_INTERVAL", "300"))  # 默认 5 分钟 (300 秒)
PUSH_TARGET = os.getenv("STEAM_PUSH_TARGET", "渥奇")  # 推送目标联系人/群
GATEWAY_URL = os.getenv("PUSH_GATEWAY_URL", "http://127.0.0.1:5005/send")
CACHE_FILE = Path("steam_mod_cache.json")

STEAM_API_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"

def fetch_steam_mod_details(mod_id: int) -> dict:
    """通过 Steam 官方 Web API 获取 MOD 最新真实数据"""
    try:
        payload = {
            "itemcount": 1,
            "publishedfileids[0]": mod_id
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.post(STEAM_API_URL, data=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            details = data.get("response", {}).get("publishedfiledetails", [])
            if details and details[0].get("result") == 1:
                item = details[0]
                return {
                    "mod_id": mod_id,
                    "title": item.get("title", "Unknown Mod"),
                    "subscriptions": int(item.get("subscriptions", 0)),
                    "favorited": int(item.get("favorited", 0)),
                    "lifetime_subscriptions": int(item.get("lifetime_subscriptions", 0)),
                    "lifetime_favorited": int(item.get("lifetime_favorited", 0)),
                    "views": int(item.get("views", 0)),
                    "time_updated": int(item.get("time_updated", 0)),
                }
    except Exception as e:
        logger.warning("Failed to fetch Steam API: %s", e)
    return None

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_cache(data: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Failed to save cache: %s", e)

def push_to_wechat(text: str) -> bool:
    """向本地微信推送网关发送战报"""
    try:
        resp = requests.post(GATEWAY_URL, json={"target": PUSH_TARGET, "text": text}, timeout=6)
        if resp.status_code == 200:
            logger.info("Successfully pushed notification to [%s] via Gateway", PUSH_TARGET)
            return True
        else:
            logger.warning("Gateway returned status %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("Failed to connect to WeChat Gateway (%s): %s", GATEWAY_URL, e)
    return False

def main():
    logger.info("==================================================")
    logger.info("Steam Workshop Monitor Started (Mod ID: %d)", WORKSHOP_ID)
    logger.info("Poll Interval: %d seconds | Target: [%s]", POLL_INTERVAL_SECONDS, PUSH_TARGET)
    logger.info("==================================================")

    while True:
        logger.info("Checking Steam Workshop data...")
        curr = fetch_steam_mod_details(WORKSHOP_ID)

        if curr:
            logger.info(
                "Fetched [%s] -> Subs: %d (Total: %d) | Favs: %d | Views: %d",
                curr["title"], curr["subscriptions"], curr["lifetime_subscriptions"],
                curr["favorited"], curr["views"]
            )

            last = load_cache()

            if last is None:
                # 首次启动：记录基线状态并发送一条上线确认通知
                save_cache(curr)
                init_msg = (
                    f"🎮【Steam 工坊监控已就绪】\n"
                    f"📦 MOD：《{curr['title']}》\n"
                    f"👥 当前订阅：{curr['subscriptions']} (历史累计: {curr['lifetime_subscriptions']})\n"
                    f"⭐ 当前收藏：{curr['favorited']}\n"
                    f"👀 页面浏览：{curr['views']}\n"
                    f"⏱️ 监控中（每 {POLL_INTERVAL_SECONDS // 60} 分钟自动巡检）"
                )
                logger.info("Cold-start baseline initialized. Sending initial status report...")
                push_to_wechat(init_msg)
            else:
                # 增量 Diff 计算
                delta_subs = curr["subscriptions"] - last.get("subscriptions", 0)
                delta_lifetime_subs = curr["lifetime_subscriptions"] - last.get("lifetime_subscriptions", 0)
                delta_favs = curr["favorited"] - last.get("favorited", 0)
                delta_views = curr["views"] - last.get("views", 0)

                if delta_subs > 0 or delta_favs > 0 or delta_lifetime_subs > 0:
                    report_lines = [f"🎉【Steam MOD 战报速递】", f"📦 MOD：《{curr['title']}》"]
                    if delta_subs > 0 or delta_lifetime_subs > 0:
                        report_lines.append(f"📈 新增订阅：+{max(delta_subs, delta_lifetime_subs)} 人！(当前有效订阅: {curr['subscriptions']})")
                    if delta_favs > 0:
                        report_lines.append(f"⭐ 新增收藏：+{delta_favs}！(总收藏: {curr['favorited']})")
                    if delta_views > 0:
                        report_lines.append(f"👀 页面新增浏览：+{delta_views} 次")
                    
                    report_text = "\n".join(report_lines)
                    logger.info("[GROWTH DETECTED] Dispatched battle report to WeChat!")
                    if push_to_wechat(report_text):
                        save_cache(curr)
                else:
                    logger.info("No new subscribers/favorites since last check. Staying quiet.")
                    # 依然更新浏览量等非关键数据
                    save_cache(curr)

        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
