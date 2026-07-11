import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.source_name = self.__class__.__name__
        self.ip_hint = ""

    def set_ip(self, ip: str):
        self.ip_hint = ip

    @abstractmethod
    def collect(self) -> list:
        ...

    def _item(self, title: str, **kwargs) -> dict:
        base = {
            "source": self.source_name,
            "title": title,
            "url": "",
            "rank": 0,
            "score": 0,
            "comments": 0,
            "author": "",
            "region": "",
            "created_at": "",
            "raw_data": "",
            "ip": self.ip_hint,
        }
        base.update(kwargs)
        return base
