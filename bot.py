# -*- coding: utf-8 -*-
"""
Discord 全球财经、Web3 加密货币与国际突发新闻实时聚合转发系统
包含:
1. 财经金融: 华尔街见闻 7x24 快讯、新浪财经 7x24 环球快讯
2. Web3 加密货币: CoinTelegraph、CoinDesk (智能中英双语)、币安重大公告
3. 全球突发大事件: CNBC 全球突发要闻 (智能中英双语)
"""

import os
import sys
import json
import time
import functools
import requests
import feedparser

# 确保控制台支持 UTF-8 输出并实时刷新
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

print = functools.partial(print, flush=True)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_news.txt")

session = requests.Session()
session.trust_env = False
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
})

def load_config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    # 优先从环境变量读取 Webhook（GitHub Actions Secrets 规范）
    env_webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if env_webhook:
        cfg["webhook_url"] = env_webhook
    if "sources" not in cfg:
        cfg["sources"] = {
            "wscn_finance": True,
            "sina_finance": True,
            "cointelegraph_web3": True,
            "coindesk_web3": True,
            "binance_web3": True,
            "cnbc_global": True
        }
    return cfg

def load_seen_ids():
    if not os.path.exists(CACHE_FILE):
        return set()
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_seen_id(news_id):
    with open(CACHE_FILE, "a", encoding="utf-8") as f:
        f.write(news_id.strip() + "\n")

def translate_to_zh(text):
    """自动将英文标题翻译为中文，提供双语对照"""
    if not text:
        return ""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": text[:500]}
        r = session.get(url, params=params, timeout=4)
        if r.status_code == 200:
            res = r.json()
            translated = "".join([part[0] for part in res[0] if part and part[0]])
            return translated
    except Exception:
        pass
    return ""

def send_discord_webhook(webhook_url, title, summary, link, source_name, color=3447003):
    """通过 Webhook 推送 Embed 格式消息到 Discord"""
    payload = {
        "username": f"快讯播报 | {source_name}",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/2965/2965879.png",
        "embeds": [
            {
                "title": title[:250],
                "url": link if link else None,
                "description": summary[:1500] if summary else "点击上方标题查看详情",
                "color": color,
                "footer": {
                    "text": f"{source_name} • 实时资讯"
                },
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        ]
    }
    try:
        resp = session.post(webhook_url, json=payload, timeout=10)
        if resp.status_code in [200, 204]:
            print(f"[已推送] [{source_name}] {title}")
            return True
        else:
            print(f"[推送失败] HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[推送异常] {e}")
    return False

# ================= 1. 财经与金融快讯 =================

def fetch_wscn():
    """华尔街见闻 7x24 全球财经实时快讯"""
    items = []
    try:
        url = "https://api-one-wscn.awtmt.com/apiv1/content/lives?channel=global-channel&limit=6"
        res = session.get(url, timeout=6).json()
        for item in res.get("data", {}).get("items", []):
            item_id = str(item.get("id"))
            title = item.get("title") or ""
            content = item.get("content_text") or ""
            display_title = title if title else (content[:50] + "...")
            link = f"https://wallstreetcn.com/live/global"
            if item_id:
                items.append({
                    "id": f"wscn_{item_id}",
                    "title": f"📈 {display_title}",
                    "summary": content[:400] if content else "无详细内容",
                    "link": link,
                    "source": "华尔街见闻 7x24",
                    "color": 15844367 # 金色
                })
    except Exception as e:
        print(f"[华尔街见闻异常] {e}")
    return items

def fetch_sina_finance():
    """新浪财经 7x24 全球环球快讯"""
    items = []
    try:
        url = "https://zhibo.sina.com.cn/api/zhibo/feed?page=1&page_size=6&zhibo_id=152"
        res = session.get(url, timeout=6).json()
        for item in res.get("result", {}).get("data", {}).get("feed", {}).get("list", []):
            item_id = str(item.get("id"))
            text = item.get("rich_text") or item.get("text") or ""
            title = text[:60] + "..." if len(text) > 60 else text
            time_str = item.get("create_time", "")
            if item_id and text:
                items.append({
                    "id": f"sina_fin_{item_id}",
                    "title": f"📊 {title}",
                    "summary": f"{text}\n\n发布时间: {time_str}",
                    "link": "https://finance.sina.com.cn/7x24/",
                    "source": "新浪财经 7x24",
                    "color": 16753920 # 橙色
                })
    except Exception as e:
        print(f"[新浪财经异常] {e}")
    return items

# ================= 2. Web3 / 加密货币快讯 =================

def fetch_cointelegraph():
    """CoinTelegraph 全球头部加密媒体 (带自动中文翻译)"""
    items = []
    try:
        url = "https://cointelegraph.com/rss"
        res = session.get(url, timeout=6)
        feed = feedparser.parse(res.content)
        for entry in feed.entries[:5]:
            orig_title = entry.get("title", "").strip()
            link = entry.get("link", "")
            summary = entry.get("summary", "").replace("<p>", "").replace("</p>", "").strip()
            if orig_title and link:
                zh_title = translate_to_zh(orig_title)
                title = f"⚡ {zh_title} ({orig_title})" if zh_title else f"⚡ {orig_title}"
                items.append({
                    "id": f"ct_{link}",
                    "title": title,
                    "summary": summary[:300] + ("..." if len(summary) > 300 else ""),
                    "link": link,
                    "source": "CoinTelegraph (Web3)",
                    "color": 16766720 # 黄色
                })
    except Exception as e:
        print(f"[CoinTelegraph异常] {e}")
    return items

def fetch_coindesk():
    """CoinDesk 权威加密资讯 (带自动中文翻译)"""
    items = []
    try:
        url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
        res = session.get(url, timeout=6)
        feed = feedparser.parse(res.content)
        for entry in feed.entries[:5]:
            orig_title = entry.get("title", "").strip()
            link = entry.get("link", "")
            summary = entry.get("summary", "").strip()
            if orig_title and link:
                zh_title = translate_to_zh(orig_title)
                title = f"🪙 {zh_title} ({orig_title})" if zh_title else f"🪙 {orig_title}"
                items.append({
                    "id": f"cd_{link}",
                    "title": title,
                    "summary": summary[:300] if summary else "点击查看全文",
                    "link": link,
                    "source": "CoinDesk (Web3)",
                    "color": 3066993 # 绿色
                })
    except Exception as e:
        print(f"[CoinDesk异常] {e}")
    return items

def fetch_binance():
    """币安官方公告 (新币上线与重大动态)"""
    items = []
    try:
        url = "https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query?catalogId=48&pageNo=1&pageSize=5"
        res = session.get(url, timeout=6).json()
        for art in res.get("data", {}).get("articles", []):
            code = str(art.get("code"))
            title = art.get("title", "").strip()
            link = f"https://www.binance.com/zh-CN/support/announcement/{code}"
            if code and title:
                items.append({
                    "id": f"bn_{code}",
                    "title": f"🔶 币安公告: {title}",
                    "summary": f"币安官方最新公告发布，点击链接查看全文。",
                    "link": link,
                    "source": "Binance 官方",
                    "color": 15844367 # 币安黄
                })
    except Exception as e:
        print(f"[币安公告异常] {e}")
    return items

# ================= 3. 全球与国际大事件 =================

def fetch_cnbc():
    """CNBC 全球突发与宏观大事件 (带自动中文翻译)"""
    items = []
    try:
        url = "https://www.cnbc.com/id/100003114/device/rss/rss.html"
        res = session.get(url, timeout=6)
        feed = feedparser.parse(res.content)
        for entry in feed.entries[:5]:
            orig_title = entry.get("title", "").strip()
            link = entry.get("link", "")
            summary = entry.get("summary", "").strip()
            if orig_title and link:
                zh_title = translate_to_zh(orig_title)
                title = f"🌍 {zh_title} ({orig_title})" if zh_title else f"🌍 {orig_title}"
                items.append({
                    "id": f"cnbc_{link}",
                    "title": title,
                    "summary": summary[:300] if summary else "点击查看详情",
                    "link": link,
                    "source": "CNBC 全球突发",
                    "color": 3447003 # 蓝色
                })
    except Exception as e:
        print(f"[CNBC异常] {e}")
    return items

# ================= 主控制循环 =================

def main():
    config = load_config()
    webhook_url = config.get("webhook_url", "").strip()
    interval = config.get("check_interval_seconds", 60)
    sources_cfg = config.get("sources", {})

    print("=" * 65)
    print("【全网多源快讯聚合系统】正在运行...")
    print(f"数据源配置:")
    for k, v in sources_cfg.items():
        print(f" - {k}: {'启用' if v else '关闭'}")
    print(f"轮询检查周期: {interval} 秒")
    print("=" * 65)

    seen_ids = load_seen_ids()
    is_first_run = (len(seen_ids) == 0)

    while True:
        all_news = []

        # 1. 财经金融
        if sources_cfg.get("wscn_finance", True):
            all_news.extend(fetch_wscn())
        if sources_cfg.get("sina_finance", True):
            all_news.extend(fetch_sina_finance())

        # 2. Web3 / 加密货币
        if sources_cfg.get("cointelegraph_web3", True):
            all_news.extend(fetch_cointelegraph())
        if sources_cfg.get("coindesk_web3", True):
            all_news.extend(fetch_coindesk())
        if sources_cfg.get("binance_web3", True):
            all_news.extend(fetch_binance())

        # 3. 全球突发大事件
        if sources_cfg.get("cnbc_global", True):
            all_news.extend(fetch_cnbc())

        # 首次启动：记录已有快照，并向各大分类分别推送 1 条样例
        if is_first_run:
            print("[首次启动] 正在录入现有快讯快照，避免刷屏...")
            pushed_categories = set()
            for item in all_news:
                seen_ids.add(item["id"])
                save_seen_id(item["id"])
                cat = item["source"]
                if cat not in pushed_categories:
                    send_discord_webhook(
                        webhook_url=webhook_url,
                        title=item["title"],
                        summary=item["summary"],
                        link=item["link"],
                        source_name=item["source"],
                        color=item["color"]
                    )
                    pushed_categories.add(cat)
                    time.sleep(1)
            is_first_run = False
        else:
            # 持续监控新增快讯
            for item in all_news:
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    save_seen_id(item["id"])
                    send_discord_webhook(
                        webhook_url=webhook_url,
                        title=item["title"],
                        summary=item["summary"],
                        link=item["link"],
                        source_name=item["source"],
                        color=item["color"]
                    )
                    time.sleep(1)

        if "--once" in sys.argv:
            print("单次检查完成 (--once)，正常退出。")
            break
        time.sleep(interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n新闻服务已停止。")
