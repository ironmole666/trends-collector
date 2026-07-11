import xml.etree.ElementTree as ET
import logging
import requests
from .base import BaseCollector

logger = logging.getLogger(__name__)


class GoogleTrendsCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self.source_name = "google_trends"
        self.regions = config.get("regions", ["US", "GB", "JP"])
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
            "Accept": "application/atom+xml, application/xml, text/xml, */*",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def collect(self) -> list:
        all_items = []
        for geo in self.regions:
            try:
                items = self._fetch_region(geo)
                if not items:
                    logger.warning(f"[Google Trends {geo}] RSS returned 0 entries "
                                   "(可能被 IP 限制，尝试替代端点)")
                all_items.extend(items)
            except Exception as e:
                logger.error(f"[Google Trends {geo}] Failed: {e}")
        return all_items

    def _fetch_region(self, geo: str) -> list:
        url = f"https://trends.google.com/trending/rss?geo={geo}"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()

        # 如果 RSS 返回空，尝试日志记录响应前 200 字节辅助调试
        if not resp.content or len(resp.content) < 100:
            logger.warning(f"[Google Trends {geo}] RSS response too short: {resp.content[:200]}")
            return self._fallback_daily(geo)

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            logger.warning(f"[Google Trends {geo}] XML parse error: {e}")
            return self._fallback_daily(geo)

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall(".//atom:entry", ns)

        if not entries:
            logger.warning(f"[Google Trends {geo}] RSS returned 0 atom:entry elements, "
                           f"content len={len(resp.content)}, "
                           f"first 100 chars: {resp.content[:100]}")
            return self._fallback_daily(geo)

        items = []
        for i, entry in enumerate(entries, 1):
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            title = title_el.text if title_el is not None else "N/A"
            url = link_el.get("href") if link_el is not None else ""

            traffic_el = entry.find("{http://schemas.google.com/themes/2005}approx_traffic")
            score = 0
            if traffic_el is not None and traffic_el.text:
                score = self._parse_traffic(traffic_el.text)

            items.append(self._item(
                title=title, url=url, rank=i, score=score, region=geo,
                raw_data=f"{{'geo':'{geo}','rank':{i}}}"
            ))
        return items

    def _fallback_daily(self, geo: str) -> list:
        """
        如果 RSS 端点不可用，尝试 Google Trends 日报页面。
        返回一个空列表（暂不做 HTML 解析，保持稳定）。
        """
        logger.info(f"[Google Trends {geo}] RSS unavailable, no fallback available")
        return []

    @staticmethod
    def _parse_traffic(text: str) -> int:
        text = text.replace(",", "").replace("+", "").strip()
        if "K" in text:
            return int(float(text.replace("K", "")) * 1000)
        if "M" in text:
            return int(float(text.replace("M", "")) * 1000000)
        try:
            return int(text)
        except ValueError:
            return 0
