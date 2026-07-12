"""
Optional title translation via DeepL API (free tier).
Used when generating the daily report.
API: https://www.deepl.com/pro#developer (Free: 500K chars/month)
"""

import logging
import requests

logger = logging.getLogger(__name__)


class Translator:
    def __init__(self, config: dict):
        self.enabled = config.get("enabled", False)
        self.api_key = config.get("api_key", "")
        self.target_lang = config.get("target_lang", "ZH")

    def translate(self, text: str) -> str:
        """Translate a single text to target language.
        Returns original text if translation fails or is disabled."""
        if not self.enabled or not self.api_key or not text:
            return text

        # Don't translate very short text, URLs, or code-like content
        text_stripped = text.strip()
        if len(text_stripped) < 4:
            return text
        if text_stripped.startswith("http://") or text_stripped.startswith("https://"):
            return text
        if text_stripped.startswith("[") and "]" in text_stripped:
            # GitHub-style "[owner/repo] description" — only translate the description part
            bracket_end = text_stripped.index("]")
            prefix = text_stripped[: bracket_end + 1]
            rest = text_stripped[bracket_end + 1 :].strip()
            if rest:
                translated = self._call_api(rest)
                if translated:
                    return f"{prefix} {translated}"
            return text

        translated = self._call_api(text_stripped)
        return translated if translated else text

    def _call_api(self, text: str) -> str | None:
        """Call DeepL API to translate a single text."""
        try:
            resp = requests.post(
                "https://api-free.deepl.com/v2/translate",
                json={"text": [text], "target_lang": self.target_lang},
                headers={
                    "Authorization": f"DeepL-Auth-Key {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()["translations"][0]["text"]
            elif resp.status_code == 403:
                logger.error("DeepL auth failed — check api_key")
            else:
                logger.warning(f"DeepL API error: HTTP {resp.status_code}")
            return None
        except requests.exceptions.Timeout:
            logger.warning("DeepL API timed out")
            return None
        except Exception as e:
            logger.warning(f"DeepL translation error: {e}")
            return None
