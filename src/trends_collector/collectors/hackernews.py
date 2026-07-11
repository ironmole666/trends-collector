import logging
import requests
from .base import BaseCollector

logger = logging.getLogger(__name__)


class HackerNewsCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self.source_name = "hackernews"
        self.limit = config.get("limit", 30)

    def collect(self) -> list:
        url = "https://hn.algolia.com/api/v1/search_by_date"
        params = {"tags": "front_page", "hitsPerPage": self.limit}

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", [])
        except Exception as e:
            logger.error(f"[HackerNews] Failed: {e}")
            return []

        items = []
        for i, item in enumerate(hits, 1):
            title = item.get("title", "N/A")
            story_url = item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID', '')}"
            author = item.get("author", "")
            score = item.get("points", 0)
            comments = item.get("num_comments", 0)
            created = item.get("created_at", "")

            items.append(self._item(
                title=title, url=story_url, rank=i, score=score,
                comments=comments, author=author, created_at=created,
            ))
        return items
