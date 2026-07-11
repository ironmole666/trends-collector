from .base import BaseCollector
from .google_trends import GoogleTrendsCollector
from .reddit import RedditCollector
from .hackernews import HackerNewsCollector
from .youtube import YouTubeCollector
from .github import GitHubCollector

__all__ = [
    "BaseCollector",
    "GoogleTrendsCollector",
    "RedditCollector",
    "HackerNewsCollector",
    "YouTubeCollector",
    "GitHubCollector",
]
