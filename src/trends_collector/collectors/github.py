"""
GitHub trending repositories collector.
Scrapes https://github.com/trending (no API key, no rate limits).
Falls back to GitHub Search API as last resort.
"""

import logging
import re
from datetime import datetime, timedelta
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
        html = resp.text

        # 如果是反爬页面，截取片段到日志辅助诊断
        if "Trending" not in html and "trending" not in html:
            snippet = html[:300].replace("\n", " ").strip()
            logger.warning(f"[GitHub {language}] Not trending page, snippet={snippet}")
            return self._fallback_search(language)

        items = []

        # 方式一：尝试解析 <h2 class="h3"> 容器（GitHub 2024+ 新版 layout）
        # 新版 trending 页面可能不使用 <article>, 改用 <div class="Box-row">
        rows = re.findall(
            r'<div\s+class="Box-row[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</li>',
            html, re.DOTALL
        )
        if not rows:
            # 方式二：尝试旧格式 <article class="Box-row">
            rows = re.findall(
                r'<article\s+class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>',
                html, re.DOTALL
            )
        if not rows:
            # 方式三：最简单的粗暴方法 - 找所有 h2 > a 链接到仓库的
            rows = re.findall(
                r'<h[23][^>]*>.*?<a\s+href="/([^"/]+/[^"/]+)"[^>]*>.*?</h[23]>',
                html, re.DOTALL
            )
            if rows:
                for i, full_name in enumerate(rows, 1):
                    items.append(self._item(
                        title=f"[{full_name}]",
                        url=f"https://github.com/{full_name}",
                        rank=i, score=0, region=language,
                    ))
                logger.info(f"[GitHub {language}] parsed {len(items)} repos (mode 3)")
                return items

        for i, row in enumerate(rows, 1):
            # Repo name
            name_match = re.search(
                r'href="/([^"/]+/[^"/]+)"',
                row
            )
            if not name_match:
                continue
            full_name = name_match.group(1)

            # Description (optional <p>)
            desc_match = re.search(
                r'<p[^>]*>\s*(.*?)\s*</p>',
                row, re.DOTALL
            )
            description = ""
            if desc_match:
                description = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
                description = re.sub(r'\s+', ' ', description)

            # Stars (look for svg.octicon-star + following text)
            stars = 0
            stars_match = re.search(
                r'(\d[\d,]*)\s*<a[^>]*>[\s\S]{0,50}star',
                row, re.IGNORECASE
            )
            if not stars_match:
                stars_match = re.search(
                    r'star[\s\S]{0,50}(\d[\d,]*)',
                    row, re.IGNORECASE
                )
            if stars_match:
                try:
                    stars = int(stars_match.group(1).replace(",", ""))
                except ValueError:
                    stars = 0

            title = f"[{full_name}] {description}" if description else f"[{full_name}]"
            repo_url = f"https://github.com/{full_name}"

            items.append(self._item(
                title=title[:200], url=repo_url, rank=i,
                score=stars, region=language,
            ))

        if items:
            logger.info(f"[GitHub {language}] parsed {len(items)} repos")
        else:
            logger.warning(f"[GitHub {language}] all parsing modes failed, "
                           f"trying Search API fallback")
            return self._fallback_search(language)

        return items

    def _fallback_search(self, language: str) -> list:
        """
        最终兜底：用 GitHub Search API，限定每轮只查第一个语言，
        避免耗尽 60 req/hour 的共享额度。
        """
        # 只在 python 语言上尝试 API，其他语言直接跳过
        if language != self.languages[0]:
            return []

        since = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        url = "https://api.github.com/search/repositories"
        params = {
            "q": f"language:{language} created:>{since}",
            "sort": "stars", "order": "desc", "per_page": 10,
        }
        headers = {"Accept": "application/vnd.github.v3+json"}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 403:
                logger.warning(f"[GitHub {language}] Search API rate limited")
                return []
            resp.raise_for_status()
            repos = resp.json().get("items", [])
            items = []
            for i, repo in enumerate(repos, 1):
                title = f"[{repo.get('full_name','')}] {repo.get('description','') or ''}"
                items.append(self._item(
                    title=title[:200],
                    url=repo.get("html_url", ""),
                    rank=i, score=repo.get("stargazers_count", 0),
                    region=language,
                ))
            logger.info(f"[GitHub {language}] fallback API returned {len(items)} repos")
            return items
        except Exception as e:
            logger.error(f"[GitHub {language}] fallback API failed: {e}")
            return []
