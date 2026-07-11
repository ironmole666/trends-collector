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
                          "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        })

    def collect(self) -> list:
        all_items = []
        for geo in self.regions:
            try:
                items = self._fetch_region(geo)
                all_items.extend(items)
            except Exception as e:
                logger.error(f"[Google Trends {geo}] Failed: {e}")
        return all_items

    def _fetch_region(self, geo: str) -> list:
        url = f"https://trends.google.com/trending/rss?geo={geo}"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall(".//atom:entry", ns)

        items = []
        for i, entry in enumerate(entries, 1):
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            title = title_el.text if title_el is not None else "N/A"
            url = link_el.get("href") if link_el is not None else ""

            # Extract approx search count from <ht:approx_traffic> if present
            traffic_el = entry.find("{http://schemas.google.com/themes/2005}approx_traffic")
            score = 0
            if traffic_el is not None and traffic_el.text:
                score = self._parse_traffic(traffic_el.text)

            items.append(self._item(
                title=title, url=url, rank=i, score=score, region=geo,
                raw_data=f"{{'geo':'{geo}','rank':{i}}}"
            ))
        return items

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
