"""
Wikipedia most-read articles collector.
Uses Wikimedia REST API. Requires valid User-Agent per Wikimedia policy.
Free, no auth key needed.
"""

import logging
from datetime import datetime, timezone, timedelta
import requests
from .base import BaseCollector

logger = logging.getLogger(__name__)


class WikipediaCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self.source_name = "wikipedia"
        self.languages = config.get("languages", ["en", "ja", "ko", "de", "fr", "es", "pt"])
        self.session = requests.Session()
        # Wikimedia REQUIRES a contact-identifiable User-Agent
        self.session.headers.update({
            "User-Agent": "TrendsCollector/1.0 (github.com/gitea/trends-collector; trends@collector.local)",
            "Accept": "application/json",
        })

    def collect(self) -> list:
        # API returns prev day's data, query yesterday
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y/%m/%d")
        all_items = []

        for lang in self.languages:
            try:
                items = self._fetch_top(lang, yesterday)
                all_items.extend(items)
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else "?"
                if status == 403:
                    logger.error(f"[Wikipedia {lang}] 403 - IP 被 Wikimedia API 屏蔽")
                elif status == 404:
                    logger.debug(f"[Wikipedia {lang}] Data not yet available for {yesterday}")
                else:
                    logger.error(f"[Wikipedia {lang}] HTTP {status}: {e}")
            except Exception as e:
                logger.error(f"[Wikipedia {lang}] Failed: {e}")

        return all_items

    def _fetch_top(self, lang: str, date: str) -> list:
        url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{lang}.wikipedia.org/all-access/{date}"
        resp = self.session.get(url, timeout=15)

        if resp.status_code == 404:
            return []

        resp.raise_for_status()
        data = resp.json()

        articles = data.get("items", [])
        if not articles:
            return []

        top_articles = articles[0].get("articles", [])[:20]

        items = []
        for i, article in enumerate(top_articles, 1):
            title = article.get("article", "").replace("_", " ")
            if not title or title.startswith("Special:") or title.startswith("Main_Page"):
                continue
            views = article.get("views", 0)
            url = f"https://{lang}.wikipedia.org/wiki/{article.get('article', '')}"

            items.append(self._item(
                title=title, url=url, rank=i, score=views,
                region=lang,
            ))

        return items
