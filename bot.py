# -*- coding: utf-8 -*-
"""
Discord 专业金融与投资专属资讯系统 (F1-F5 套件)
包含:
F1. 金十/华尔街宏观 7x24 (外汇、黄金、原油、美联储决议、宏观指标)
F2. 财联社/新浪电报 7x24 (A股盘面、行业政策、上市公司突发公告)
F3. 第一财经/投资精选 7x24 (机构龙虎榜、热点个股、独家研报)
F4. 路透社 (Reuters Business) (全球商业财经与跨国巨头突发，智能双语)
F5. 彭博社 (Bloomberg Markets) (华尔街顶级机构动态与市场深度，智能双语)
"""

import os
import sys
import json
import time
import functools
import requests
import feedparser

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
    env_webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if env_webhook:
        cfg["webhook_url"] = env_webhook
    if "sources" not in cfg:
        cfg["sources"] = {
            "f1_macro": True,
            "f2_telegraph": True,
            "f3_hot_invest": True,
            "f4_reuters": True,
            "f5_bloomberg": True
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
    payload = {
        "username": f"金融投资快讯 | {source_name}",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/2965/2965879.png",
        "embeds": [
            {
                "title": title[:250],
                "url": link if link else None,
                "description": summary[:1500] if summary else "点击上方标题查看详情",
                "color": color,
                "footer": {
                    "text": f"{source_name} • 实时金融行情"
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

# ================= 数据采集函数 (F1 - F5) =================

def fetch_f1_macro():
    """F1: 金十/华尔街见闻 7x24 全球宏观快讯"""
    items = []
    try:
        url = "https://api-one-wscn.awtmt.com/apiv1/content/lives?channel=global-channel&limit=6"
        res = session.get(url, timeout=6).json()
        for item in res.get("data", {}).get("items", []):
            item_id = str(item.get("id"))
            title = item.get("title") or ""
            content = item.get("content_text") or ""
            display_title = title if title else (content[:50] + "...")
            if item_id:
                items.append({
                    "id": f"f1_{item_id}",
                    "title": f"🏛️ 【宏观指标】{display_title}",
                    "summary": content[:400] if content else "无详细内容",
                    "link": "https://wallstreetcn.com/live/global",
                    "source": "金十/华尔街宏观 7x24",
                    "color": 15844367 # 金色
                })
    except Exception as e:
        print(f"[F1 宏观快讯异常] {e}")
    return items

def fetch_f2_telegraph():
    """F2: 财联社/新浪财经 7x24 盘面与公告电报"""
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
                    "id": f"f2_{item_id}",
                    "title": f"📈 【盘面电报】{title}",
                    "summary": f"{text}\n\n时间: {time_str}",
                    "link": "https://finance.sina.com.cn/7x24/",
                    "source": "财联社/新浪电报 7x24",
                    "color": 15158332 # 红色
                })
    except Exception as e:
        print(f"[F2 盘面电报异常] {e}")
    return items

def fetch_f3_hot_invest():
    """F3: 第一财经/雪球热度 投资热点与机构动向"""
    items = []
    try:
        url = "https://www.yicai.com/api/ajax/getbrieflist?page=1&pagesize=6"
        res = session.get(url, timeout=6).json()
        for item in res:
            item_id = str(item.get("id") or item.get("LiveID"))
            title = item.get("NewsTitle") or item.get("LiveTitle") or ""
            content = item.get("LiveContent") or ""
            link = f"https://m.yicai.com/brief/{item_id}.html"
            if item_id and (title or content):
                display_title = title if title else (content[:50] + "...")
                items.append({
                    "id": f"f3_{item_id}",
                    "title": f"🔥 【投资热点】{display_title}",
                    "summary": content[:400] if content else "点击链接查看深度内容",
                    "link": link,
                    "source": "第一财经/投资精选",
                    "color": 16753920 # 橙色
                })
    except Exception as e:
        print(f"[F3 投资热点异常] {e}")
    return items

def fetch_f4_reuters():
    """F4: 路透社 (Reuters Business) 全球商业与跨国企业 (智能双语)"""
    items = []
    try:
        url = "https://feeds.feedburner.com/reuters/businessNews"
        res = session.get(url, timeout=6)
        feed = feedparser.parse(res.content)
        for entry in feed.entries[:5]:
            orig_title = entry.get("title", "").strip()
            link = entry.get("link", "")
            summary = entry.get("summary", "").strip()
            if orig_title and link:
                zh_title = translate_to_zh(orig_title)
                title = f"🌐 【路透商业】{zh_title} ({orig_title})" if zh_title else f"🌐 【路透商业】{orig_title}"
                items.append({
                    "id": f"f4_{link}",
                    "title": title,
                    "summary": summary[:300] if summary else "点击查看全文",
                    "link": link,
                    "source": "路透社 (Reuters)",
                    "color": 3447003 # 宝蓝色
                })
    except Exception as e:
        print(f"[F4 路透社异常] {e}")
    return items

def fetch_f5_bloomberg():
    """F5: 彭博社 (Bloomberg Markets) 华尔街机构行情深度 (智能双语)"""
    items = []
    try:
        url = "https://feeds.bloomberg.com/markets/news.rss"
        res = session.get(url, timeout=6)
        feed = feedparser.parse(res.content)
        for entry in feed.entries[:5]:
            orig_title = entry.get("title", "").strip()
            link = entry.get("link", "")
            summary = entry.get("summary", "").strip()
            if orig_title and link:
                zh_title = translate_to_zh(orig_title)
                title = f"📊 【彭博市场】{zh_title} ({orig_title})" if zh_title else f"📊 【彭博市场】{orig_title}"
                items.append({
                    "id": f"f5_{link}",
                    "title": title,
                    "summary": summary[:300] if summary else "点击查看全文",
                    "link": link,
                    "source": "彭博社 (Bloomberg)",
                    "color": 10181046 # 紫色
                })
    except Exception as e:
        print(f"[F5 彭博社异常] {e}")
    return items

# ================= 主控制循环 =================

def main():
    config = load_config()
    webhook_url = config.get("webhook_url", "").strip()
    interval = config.get("check_interval_seconds", 60)
    sources_cfg = config.get("sources", {})

    print("=" * 65)
    print("【顶级金融与投资情报系统 F1-F5】正在运行...")
    print(f"数据源配置:")
    for k, v in sources_cfg.items():
        print(f" - {k}: {'启用' if v else '关闭'}")
    print(f"轮询检查周期: {interval} 秒")
    print("=" * 65)

    seen_ids = load_seen_ids()
    is_first_run = (len(seen_ids) == 0)

    while True:
        all_news = []

        if sources_cfg.get("f1_macro", True):
            all_news.extend(fetch_f1_macro())
        if sources_cfg.get("f2_telegraph", True):
            all_news.extend(fetch_f2_telegraph())
        if sources_cfg.get("f3_hot_invest", True):
            all_news.extend(fetch_f3_hot_invest())
        if sources_cfg.get("f4_reuters", True):
            all_news.extend(fetch_f4_reuters())
        if sources_cfg.get("f5_bloomberg", True):
            all_news.extend(fetch_f5_bloomberg())

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
