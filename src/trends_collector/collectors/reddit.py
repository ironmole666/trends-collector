import logging
from datetime import datetime
import requests
from .base import BaseCollector

logger = logging.getLogger(__name__)


class RedditCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self.source_name = "reddit"
        self.subreddits = config.get("subreddits", ["all", "worldnews", "technology"])
        self.limit = config.get("limit", 25)
        self.session = requests.Session()
        # Reddit 对 User-Agent 非常严格，用浏览器 UA + 合法描述
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/125.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        })

    def collect(self) -> list:
        all_items = []
        for sub in self.subreddits:
            try:
                items = self._fetch_subreddit(sub)
                all_items.extend(items)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 403:
                    logger.error(f"[Reddit r/{sub}] 403 Blocked - 数据中心 IP 被 Reddit 屏蔽，无解决方案")
                else:
                    logger.error(f"[Reddit r/{sub}] HTTP Error: {e}")
            except Exception as e:
                logger.error(f"[Reddit r/{sub}] Failed: {e}")
        return all_items

    def _fetch_subreddit(self, subreddit: str) -> list:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={self.limit}"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        posts = data.get("data", {}).get("children", [])

        items = []
        for i, post in enumerate(posts, 1):
            p = post.get("data", {})
            title = p.get("title", "N/A")
            permalink = p.get("permalink", "")
            url = f"https://reddit.com{permalink}"
            score = p.get("score", 0)
            comments = p.get("num_comments", 0)
            author = p.get("author", "")
            created = datetime.fromtimestamp(p.get("created_utc", 0)).isoformat()
            region = subreddit

            items.append(self._item(
                title=title, url=url, rank=i, score=score,
                comments=comments, author=author, region=region,
                created_at=created,
            ))
        return items
