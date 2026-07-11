"""
GitHub trending repositories collector.
Scrapes https://github.com/trending (no API key, no rate limits).
"""

import logging
import re
import requests
from .base import BaseCollector

logger = logging.getLogger(__name__)


class GitHubCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self.source_name = "github"
        self.languages = config.get("languages", ["python", "javascript", "go", "rust", "typescript"])
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

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
        url = f"https://github.com/trending/{language}?since=weekly"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()

        html = resp.text
        items = []

        # Parse repo cards from the trending page
        # Each repo card starts with <article class="Box-row">
        articles = re.findall(
            r'<article class="Box-row[^"]*"[^>]*>(.*?)</article>',
            html, re.DOTALL
        )

        for i, article in enumerate(articles, 1):
            # Repo name: <h2><a href="/owner/repo">
            name_match = re.search(
                r'<h[23][^>]*>.*?<a\s+href="/([^"/]+/[^"/]+)"',
                article, re.DOTALL
            )
            if not name_match:
                continue
            full_name = name_match.group(1)

            # Description
            desc_match = re.search(
                r'<p class="col-9[^"]*"[^>]*>\s*(.*?)\s*</p>',
                article, re.DOTALL
            )
            description = ""
            if desc_match:
                description = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
                # Clean up whitespace
                description = re.sub(r'\s+', ' ', description)

            # Stars count
            stars_match = re.search(
                r'<a[^>]*href="/[^"]+/stargazers"[^>]*>.*?(\d[\d,]*)\s*</a>',
                article, re.DOTALL
            )
            stars = 0
            if stars_match:
                stars = int(stars_match.group(1).replace(",", ""))

            title = f"[{full_name}] {description}" if description else f"[{full_name}]"
            repo_url = f"https://github.com/{full_name}"

            items.append(self._item(
                title=title[:200], url=repo_url, rank=i,
                score=stars, region=language,
                raw_data=f"{{'full_name':'{full_name}','lang':'{language}'}}"
            ))

        if not items:
            logger.warning(f"[GitHub {language}] No repos found in trending page")

        logger.info(f"[GitHub {language}] scraped {len(items)} trending repos")
        return items
