#!/usr/bin/env python3
"""
在能访问中国大陆网络的机器上运行。
采集国内平台热搜后推送到海外 VPS 主节点。
主节点已有 SQLite 存储和邮件通知，收到推送后自动入库。

使用方式：
  1. 将此文件放到国内机器上
  2. 按需配置 PUSH_URL（海外 VPS 的接收端点）
  3. crontab 中每 30 分钟执行一次

依赖：pip install requests lxml
"""

import json
import time
import hashlib
import requests as req

# ===== 配置 =====
PUSH_URL = "https://你的海外VPS:端口/collect"       # 海外 VPS 接收端点
PUSH_KEY = "与你海外 VPS 约定的密钥"                  # 简单鉴权
# ================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
}


def fetch_weibo_hot():
    """微博热搜"""
    url = "https://weibo.com/ajax/side/hotSearch"
    try:
        r = req.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        items = []
        for i, item in enumerate(data.get("data", {}).get("realtime", [])[:20], 1):
            title = item.get("word", "")
            score = item.get("raw_hot", 0) or item.get("num", 0)
            items.append({
                "source": "weibo",
                "title": title,
                "rank": i, "score": score,
                "url": f"https://s.weibo.com/weibo?q={title}",
                "region": "CN",
            })
        return items
    except Exception as e:
        print(f"[Weibo] Failed: {e}")
        return []


def fetch_baidu_hot():
    """百度热搜"""
    url = "https://top.baidu.com/board?tab=realtime"
    try:
        r = req.get(url, headers=HEADERS, timeout=10)
        from lxml import html
        tree = html.fromstring(r.text)
        items = []
        cards = tree.xpath('//div[contains(@class,"category-wrap")]')
        for i, card in enumerate(cards[:30], 1):
            title_el = card.xpath('.//div[contains(@class,"c-single-text-ellipsis")]/text()')
            if not title_el:
                continue
            title = title_el[0].strip()
            items.append({
                "source": "baidu",
                "title": title,
                "rank": i, "score": 0,
                "url": f"https://www.baidu.com/s?wd={title}",
                "region": "CN",
            })
        return items
    except Exception as e:
        print(f"[Baidu] Failed: {e}")
        return []


def fetch_zhihu_hot():
    """知乎热搜"""
    url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=30"
    headers = {**HEADERS, "Referer": "https://www.zhihu.com/hot"}
    try:
        r = req.get(url, headers=headers, timeout=10)
        data = r.json()
        items = []
        for i, item in enumerate(data.get("data", [])[:20], 1):
            target = item.get("target", {})
            title = target.get("title", "")
            score = target.get("follow_count", 0) or target.get("voteup_count", 0)
            url = target.get("url", f"https://www.zhihu.com/question/{target.get('id','')}")
            items.append({
                "source": "zhihu",
                "title": title,
                "rank": i, "score": score,
                "url": url,
                "region": "CN",
            })
        return items
    except Exception as e:
        print(f"[Zhihu] Failed: {e}")
        return []


def push_to_vps(items: list):
    """推送到海外 VPS 主节点"""
    if not items:
        return
    payload = {
        "key": PUSH_KEY,
        "items": items,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    try:
        r = req.post(PUSH_URL, json=payload, timeout=15, verify=False)
        print(f"Push result: {r.status_code} {r.text[:100]}")
    except Exception as e:
        print(f"Push failed: {e}")


if __name__ == "__main__":
    all_items = []
    all_items.extend(fetch_weibo_hot())
    all_items.extend(fetch_baidu_hot())
    all_items.extend(fetch_zhihu_hot())
    all_items.extend(fetch_weibo_hot())  # 可再加其他源

    # 去重（同一个标题只推一次）
    seen = set()
    deduped = []
    for item in all_items:
        key = item["title"]
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    print(f"Collected {len(deduped)} items from China sources")
    push_to_vps(deduped)
