"""
Notification dispatcher: Telegram and/or email.
Email uses stdlib smtplib -- zero extra dependencies.
"""

import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.header import Header

import requests

logger = logging.getLogger(__name__)


class _TelegramChannel:
    def __init__(self, config: dict):
        cfg = config.get("telegram", {})
        self.enabled = cfg.get("enabled", False)
        self.bot_token = cfg.get("bot_token", "")
        self.chat_id = cfg.get("chat_id", "")

    def send(self, text: str):
        if not (self.enabled and self.bot_token and self.chat_id):
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            resp = requests.post(url, json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }, timeout=10)
            if resp.status_code != 200:
                logger.error(f"Telegram send failed: {resp.text}")
        except Exception as e:
            logger.error(f"Telegram connection failed: {e}")


class _EmailChannel:
    def __init__(self, config: dict):
        cfg = config.get("email", {})
        self.enabled = cfg.get("enabled", False)
        self.host = cfg.get("smtp_host", "")
        self.port = cfg.get("smtp_port", 587)
        self.user = cfg.get("smtp_user", "")
        self.password = cfg.get("smtp_password", "")
        self.use_tls = cfg.get("smtp_use_tls", True)
        self.from_addr = cfg.get("from_addr", "")
        self.to_addrs = cfg.get("to_addrs", [])

    def send(self, text: str, subject: str = "TrendsCollector Summary"):
        if not (self.enabled and self.host and self.user and self.password
                and self.from_addr and self.to_addrs):
            return

        msg = MIMEText(text, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)

        try:
            if self.use_tls:
                # STARTTLS on port 587
                with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                    server.ehlo()
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                    server.login(self.user, self.password)
                    server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            else:
                # SSL on port 465
                with smtplib.SMTP_SSL(self.host, self.port, timeout=15,
                                      context=ssl.create_default_context()) as server:
                    server.login(self.user, self.password)
                    server.sendmail(self.from_addr, self.to_addrs, msg.as_string())

            logger.info(f"Email sent to {self.to_addrs} via {self.host}:{self.port}")
        except smtplib.SMTPAuthenticationError:
            logger.error("Email auth failed -- check smtp_user / smtp_password")
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"Email recipients refused: {e}")
        except smtplib.SMTPServerDisconnected:
            logger.error("Email server disconnected -- check host/port/TLS settings")
        except Exception as e:
            logger.error(f"Email send failed: {e}")


class Notifier:
    """Dispatches notifications to all configured channels."""

    def __init__(self, config: dict):
        notif_cfg = config.get("notifications", {})
        self._telegram = _TelegramChannel(notif_cfg)
        self._email = _EmailChannel(notif_cfg)

    # -- public API -------------------------------------------------------

    def send_summary(self, stats: dict, top_items: list):
        text = self._format_summary(stats, top_items)
        self._telegram.send(text)
        self._email.send(text, subject="TrendsCollector Summary")

    def send_error(self, message: str):
        body = f"\u26a0\ufe0f TrendsCollector Error\n{message}"
        self._telegram.send(body)
        self._email.send(body, subject="TrendsCollector Error")

    # -- formatting -------------------------------------------------------

    @staticmethod
    def _format_summary(stats: dict, top_items: list) -> str:
        from datetime import datetime
        lines = [
            f"TrendsCollector Summary ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
            f"Total items collected (24h): {stats.get('total', 0)}",
        ]

        by_source = stats.get("by_source", {})
        if by_source:
            lines.append("")
            for src, cnt in sorted(by_source.items(), key=lambda x: -x[1]):
                lines.append(f"  {src}: {cnt}")

        if top_items:
            lines.extend(["", "Top items:"])
            for item in top_items[:10]:
                title = item.get("title", "")[:70]
                score = item.get("score", 0)
                source = item.get("source", "")
                url = item.get("url", "")
                lines.append(f"  [{score:>8}] [{source}] {title}")
                if url:
                    lines.append(f"           {url}")

        return "\n".join(lines)
