"""
Google Trends collector with fallback chain:
  1. RSS feed (geo=US)
  2. Daily Trends JSON API (primary fallback for data center IPs)
     https://trends.google.com/trends/api/dailytrends
"""

import json
import logging
import re
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
import requests
from .base import BaseCollector

logger = logging.getLogger(__name__)


class GoogleTrendsCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self.source_name = "google_trends"
        self.regions = config.get("regions", ["US", "GB", "JP", "KR", "CA", "AU", "DE", "FR", "BR", "IN"])
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/125.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://trends.google.com/",
        })

    def collect(self) -> list:
        # 先请求首页设置 cookies，某些 Google 端点需要
        self._init_cookies()

        all_items = []
        for geo in self.regions:
            try:
                items = self._fetch_region(geo)
                all_items.extend(items)
            except Exception as e:
                logger.error(f"[Google Trends {geo}] Failed: {e}")
        return all_items

    def _init_cookies(self):
        """Set initial cookies by visiting Google Trends homepage."""
        try:
            self.session.get(
                "https://trends.google.com/trending",
                timeout=10
            )
        except Exception:
            pass  # non-critical, API may still work

    def _fetch_region(self, geo: str) -> list:
        # ---- 策略 1: RSS（数据中心 IP 可能返回空） ----
        items = self._try_rss(geo)
        if items:
            return items

        # ---- 策略 2: Daily Trends JSON API ----
        logger.info(f"[Google Trends {geo}] RSS empty, trying Daily API...")
        items = self._try_daily_api(geo)
        if items:
            return items

        # ---- 策略 3: Realtime Trends JSON API ----
        logger.info(f"[Google Trends {geo}] Daily API empty, trying Realtime API...")
        items = self._try_realtime_api(geo)
        if items:
            return items

        logger.warning(f"[Google Trends {geo}] all strategies failed")
        return []

    # ====================================================================
    # 策略 1: RSS
    # ====================================================================

    def _try_rss(self, geo: str) -> list:
        url = f"https://trends.google.com/trending/rss?geo={geo}"
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[Google Trends {geo}] RSS request failed: {e}")
            return []

        if len(resp.content) < 50:
            return []

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            return []

        # Try Atom namespace first, then RSS namespace
        ns_atom = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall(".//atom:entry", ns_atom)

        if not entries:
            # Try standard RSS <item>
            entries_xml = root.findall(".//item")
            if entries_xml:
                items = []
                for i, entry in enumerate(entries_xml, 1):
                    title_el = entry.find("title")
                    link_el = entry.find("link")
                    title = title_el.text if title_el is not None else "N/A"
                    url = link_el.text if link_el is not None else ""
                    items.append(self._item(
                        title=title, url=url, rank=i, region=geo,
                    ))
                logger.info(f"[Google Trends {geo}] RSS (RSS format) parsed {len(items)} items")
                return items
            return []

        items = []
        for i, entry in enumerate(entries, 1):
            title_el = entry.find("atom:title", ns_atom)
            link_el = entry.find("atom:link", ns_atom)
            title = title_el.text if title_el is not None else "N/A"
            link_url = link_el.get("href") if link_el is not None else ""

            traffic_el = entry.find("{http://schemas.google.com/themes/2005}approx_traffic")
            score = 0
            if traffic_el is not None and traffic_el.text:
                score = self._parse_traffic(traffic_el.text)

            items.append(self._item(
                title=title, url=link_url, rank=i, score=score, region=geo,
            ))

        if items:
            logger.info(f"[Google Trends {geo}] RSS (Atom format) parsed {len(items)} items")
        return items

    # ====================================================================
    # 策略 2: Daily Trends JSON API
    # ====================================================================

    def _try_daily_api(self, geo: str) -> list:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        url = (
            "https://trends.google.com/trends/api/dailytrends"
            f"?hl=en-US&tz=-480&ed={today}&geo={geo}"
        )
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[Google Trends {geo}] Daily API request failed: {e}")
            return []

        data = self._parse_api_response(resp.text)
        if not data:
            return []

        trending = data.get("trendingSearches", [])
        if not trending:
            return []

        items = []
        for i, entry in enumerate(trending, 1):
            title_info = entry.get("title", {})
            title = title_info.get("query", "N/A")
            traffic = entry.get("formattedTraffic", "")
            score = 0
            if traffic:
                score = self._parse_traffic(traffic)

            articles = entry.get("articles", [])
            url = articles[0].get("url", "") if articles else ""

            items.append(self._item(
                title=title, url=url, rank=i, score=score, region=geo,
            ))

        if items:
            logger.info(f"[Google Trends {geo}] Daily API returned {len(items)} items")
        return items

    # ====================================================================
    # 策略 3: Realtime Trends JSON API
    # ====================================================================

    def _try_realtime_api(self, geo: str) -> list:
        url = (
            "https://trends.google.com/trends/api/realtimetrends"
            f"?hl=en-US&tz=-480&geo={geo}"
        )
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[Google Trends {geo}] Realtime API request failed: {e}")
            return []

        data = self._parse_api_response(resp.text)
        if not data:
            return []

        # 实时趋势的结构不同：storySummaries -> trendingStories
        stories = []
        summaries = data.get("storySummaries", {})
        if isinstance(summaries, dict):
            stories = summaries.get("trendingStories", [])

        if not stories:
            return []

        items = []
        for i, story in enumerate(stories, 1):
            title = story.get("title", "N/A")
            articles = story.get("articles", [])
            url = articles[0].get("url", "") if articles else ""
            score = story.get("entityNames", [])
            items.append(self._item(
                title=title, url=url, rank=i, score=len(score), region=geo,
            ))

        logger.info(f"[Google Trends {geo}] Realtime API returned {len(items)} items")
        return items

    # ====================================================================
    # Helpers
    # ====================================================================

    @staticmethod
    def _parse_api_response(text: str) -> dict:
        """Strip the )]}' prefix and parse JSON."""
        # Remove )]}' prefix that Google adds for XSSI protection
        cleaned = re.sub(r"^\)\]\}'\s*", "", text, count=1).strip()
        if not cleaned:
            return {}
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"Google Trends API JSON parse error: {e}, text={text[:200]}")
            return {}

    @staticmethod
    def _parse_traffic(text: str) -> int:
        text = text.replace(",", "").replace("+", "").strip()
        if "K" in text:
            return int(float(text.replace("K", "")) * 1000)
        if "M" in text:
            return int(float(text.replace("M", "")) * 1000000)
        if "B" in text:
            return int(float(text.replace("B", "")) * 1000000000)
        try:
            return int(text)
        except ValueError:
            return 0
