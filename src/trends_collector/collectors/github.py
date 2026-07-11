import logging
from datetime import datetime, timedelta
import requests
from .base import BaseCollector

logger = logging.getLogger(__name__)


class GitHubCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self.source_name = "github"
        self.languages = config.get("languages", ["python", "javascript", "go", "rust", "typescript"])

    def collect(self) -> list:
        all_items = []
        for lang in self.languages:
            try:
                items = self._fetch_trending(lang)
                all_items.extend(items)
            except Exception as e:
                logger.error(f"[GitHub {lang}] Failed: {e}")
        return all_items

    def _fetch_trending(self, language: str) -> list:
        # GitHub Search API 不支持 ">7days"，必须用具体日期
        since = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

        url = "https://api.github.com/search/repositories"
        params = {
            "q": f"language:{language} created:>{since}",
            "sort": "stars",
            "order": "desc",
            "per_page": 10,
        }
        headers = {"Accept": "application/vnd.github.v3+json"}
        resp = requests.get(url, params=params, headers=headers, timeout=15)

        if resp.status_code == 403:
            logger.warning("[GitHub] API rate limited, skipping")
            return []
        if resp.status_code == 422:
            logger.warning(f"[GitHub] 422 for {language}: {resp.text[:200]}")
            return []

        resp.raise_for_status()
        data = resp.json()
        repos = data.get("items", [])

        items = []
        for i, repo in enumerate(repos, 1):
            title = f"[{repo.get('full_name', '')}] {repo.get('description', '') or 'No description'}"
            url = repo.get("html_url", "")
            score = repo.get("stargazers_count", 0)
            author = repo.get("owner", {}).get("login", "")
            created = repo.get("created_at", "")
            region = language

            items.append(self._item(
                title=title[:200], url=url, rank=i, score=score,
                author=author, region=region, created_at=created,
            ))
        return items
