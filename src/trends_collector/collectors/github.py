"""
GitHub trending repositories collector.
Scrapes https://github.com/trending (no API key, no rate limits).
Falls back to simpler parsing if the page structure differs.
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
            "Accept-Language": "en-US,en;q=0.9",
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

        # 检测是否是反爬页面
        if "trending repositories" not in resp.text and "Trending" not in resp.text:
            logger.warning(f"[GitHub {language}] Response doesn't look like trending page "
                           f"(len={len(resp.text)}, snippet={resp.text[:200]})")
            # 尝试方式二：raw.githubusercontent.com 上的第三方趋势 API 替代
            alt_items = self._fallback_api(language)
            if alt_items:
                return alt_items
            return []

        html = resp.text
        items = []

        # 方式一：<article> 容器解析
        articles = re.findall(
            r'<article\s+class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>',
            html, re.DOTALL
        )

        for i, article in enumerate(articles, 1):
            name_match = re.search(
                r'<h[23][^>]*>.*?<a\s+href="/([^"/]+/[^"/]+)"',
                article, re.DOTALL
            )
            if not name_match:
                continue
            full_name = name_match.group(1)

            desc_match = re.search(
                r'<p\s+class="col-9[^"]*"[^>]*>\s*(.*?)\s*</p>',
                article, re.DOTALL
            )
            description = ""
            if desc_match:
                description = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
                description = re.sub(r'\s+', ' ', description)

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

        if items:
            logger.info(f"[GitHub {language}] scraped {len(items)} trending repos")
        else:
            # 方式二：尝试第三方 API 作为兜底
            logger.info(f"[GitHub {language}] article parsing returned 0, trying fallback")
            alt_items = self._fallback_api(language)
            if alt_items:
                return alt_items
            logger.warning(f"[GitHub {language}] No repos found")

        return items

    def _fallback_api(self, language: str) -> list:
        """
        替代方案：使用 gh-trending-api 第三方服务或简单的行解析。
        目前返回空列表，后续可接入可靠的三方 API。
        """
        logger.info(f"[GitHub {language}] No fallback API configured")
        return []
