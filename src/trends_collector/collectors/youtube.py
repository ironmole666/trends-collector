import logging
import requests
from .base import BaseCollector

logger = logging.getLogger(__name__)


class YouTubeCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self.source_name = "youtube"
        self.api_key = config.get("api_key", "")
        self.regions = config.get("regions", ["US", "JP"])

    def is_available(self) -> bool:
        return bool(self.api_key)

    def collect(self) -> list:
        if not self.api_key:
            logger.warning("[YouTube] No API key configured, skipping")
            return []

        all_items = []
        for region in self.regions:
            try:
                items = self._fetch_region(region)
                all_items.extend(items)
            except Exception as e:
                logger.error(f"[YouTube {region}] Failed: {e}")
        return all_items

    def _fetch_region(self, region: str) -> list:
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": region,
            "maxResults": 15,
            "key": self.api_key,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        videos = data.get("items", [])

        items = []
        for i, v in enumerate(videos, 1):
            snip = v.get("snippet", {})
            stats = v.get("statistics", {})
            title = snip.get("title", "N/A")
            video_url = f"https://www.youtube.com/watch?v={v.get('id', '')}"
            score = int(stats.get("viewCount", 0))
            author = snip.get("channelTitle", "")
            created = snip.get("publishedAt", "")

            items.append(self._item(
                title=title, url=video_url, rank=i, score=score,
                author=author, region=region, created_at=created,
            ))
        return items
