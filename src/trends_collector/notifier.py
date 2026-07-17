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

    def missing_config(self) -> list[str]:
        required = {
            "smtp_host": self.host,
            "smtp_user": self.user,
            "smtp_password": self.password,
            "from_addr": self.from_addr,
            "to_addrs": self.to_addrs,
        }
        return [name for name, value in required.items() if not value]

    def is_ready(self) -> bool:
        return self.enabled and not self.missing_config()

    def send(self, text: str, subject: str = "TrendsCollector Summary"):
        if not self.is_ready():
            return False

        msg = MIMEText(text, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)

        try:
            if self.use_tls:
                with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                    server.ehlo()
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                    server.login(self.user, self.password)
                    server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            else:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=15,
                                      context=ssl.create_default_context()) as server:
                    server.login(self.user, self.password)
                    server.sendmail(self.from_addr, self.to_addrs, msg.as_string())

            logger.info(f"Email sent to {self.to_addrs} via {self.host}:{self.port}")
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error("Email auth failed -- check smtp_user / smtp_password")
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"Email recipients refused: {e}")
        except smtplib.SMTPServerDisconnected:
            logger.error("Email server disconnected -- check host/port/TLS settings")
        except Exception as e:
            logger.error(f"Email send failed: {e}")
        return False


class _HttpEmailChannel:
    """Sends email via HTTPS API (SendGrid, Resend, Mailjet, etc.).
    Works when SMTP ports are blocked (NAT VPS).
    Goes through port 443 so it works on any VPS."""

    # Provider templates: url, payload builder, response check
    _PROVIDERS = {
        "sendgrid": {
            "url": "https://api.sendgrid.com/v3/mail/send",
            "build": lambda subj, text, sender, to: {
                "personalizations": [{"to": [{"email": a} for a in to]}],
                "from": {"email": sender},
                "subject": subj,
                "content": [{"type": "text/plain", "value": text}],
            },
            "headers": lambda key: {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            "auth_err": lambda c: "SendGrid auth failed" if c == 401 else None,
        },
        "resend": {
            "url": "https://api.resend.com/emails",
            "build": lambda subj, text, sender, to: {
                "from": sender,
                "to": to if len(to) > 1 else to[0],
                "subject": subj,
                "text": text,
            },
            "headers": lambda key: {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            "auth_err": lambda c: "Resend auth failed" if c == 401 else None,
        },
    }

    def __init__(self, config: dict):
        cfg = config.get("http_email", {})
        self.enabled = cfg.get("enabled", False)
        self.api_key = cfg.get("api_key", "")
        self.provider = cfg.get("provider", "sendgrid")
        self.from_addr = cfg.get("from_addr", "")
        self.to_addrs = cfg.get("to_addrs", [])

    def missing_config(self) -> list[str]:
        required = {
            "api_key": self.api_key,
            "from_addr": self.from_addr,
            "to_addrs": self.to_addrs,
        }
        missing = [name for name, value in required.items() if not value]
        if self.provider not in self._PROVIDERS:
            missing.append(f"supported provider (got {self.provider!r})")
        return missing

    def is_ready(self) -> bool:
        return self.enabled and not self.missing_config()

    def send(self, text: str, subject: str = "TrendsCollector Report"):
        if not self.is_ready():
            return False

        tmpl = self._PROVIDERS.get(self.provider)
        if not tmpl:
            logger.error(f"Unknown HTTP email provider: {self.provider}")
            return False

        url = tmpl["url"]
        payload = tmpl["build"](subject, text, self.from_addr, self.to_addrs)
        headers = tmpl["headers"](self.api_key)

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            code = resp.status_code
            auth_msg = tmpl["auth_err"](code)
            if auth_msg:
                logger.error(f"{auth_msg} -- check api_key")
            elif code == 403:
                logger.error(f"HTTP email 403 -- sender {self.from_addr} not verified")
            elif code not in (200, 201, 202):
                logger.error(f"HTTP email API error: HTTP {code} {resp.text[:200]}")
            else:
                logger.info(f"Email sent via {self.provider} API to {self.to_addrs}")
                return True
        except Exception as e:
            logger.error(f"HTTP email API request failed: {e}")
        return False


class Notifier:
    """Dispatches notifications to all configured channels."""

    def __init__(self, config: dict):
        notif_cfg = config.get("notifications", {})
        self._telegram = _TelegramChannel(notif_cfg)
        self._email = _EmailChannel(notif_cfg)
        self._http_email = _HttpEmailChannel(notif_cfg)
        self._storage = None
        self._log_email_config_warnings()

    def _log_email_config_warnings(self):
        channels = (
            ("SMTP email", self._email),
            ("HTTP email", self._http_email),
        )
        for label, channel in channels:
            if channel.enabled and not channel.is_ready():
                logger.warning(
                    f"{label} enabled but incomplete; missing: "
                    f"{', '.join(channel.missing_config())}"
                )

    def set_storage(self, storage):
        self._storage = storage

    def send_summary(self, stats: dict, top_items: list, full_report: str = None):
        """Send collection summary.
        Telegram gets short summary (4096 char limit).
        Email gets the full daily report if available.
        HTTP relay gets the full report (for VPS A to forward via SMTP).
        """
        short_text = self._format_summary(stats, top_items)
        self._telegram.send(short_text)

        email_text = full_report or short_text
        subject = "TrendsCollector Report" if full_report else "TrendsCollector Summary"
        self._send_email_with_fallback(email_text, subject)

    def send_error(self, message: str):
        body = f"\u26a0\ufe0f TrendsCollector Error\n{message}"
        self._telegram.send(body)
        self._send_email_with_fallback(body, "TrendsCollector Error")

    def _send_email_with_fallback(self, text: str, subject: str) -> bool:
        """Try every ready email channel in priority order until one succeeds."""
        ready_channels = []
        if self._email.is_ready():
            ready_channels.append(("SMTP", self._email))
        if self._http_email.is_ready():
            ready_channels.append(("HTTP", self._http_email))

        if not ready_channels:
            logger.warning(
                "No usable email channel configured "
                "(channels are disabled or missing required settings)"
            )
            return False

        for index, (label, channel) in enumerate(ready_channels):
            if channel.send(text, subject):
                return True
            if index < len(ready_channels) - 1:
                logger.warning(f"{label} email failed; trying next configured channel")

        logger.error("All configured email channels failed")
        return False

    def _format_summary(self, stats: dict, top_items: list) -> str:
        from datetime import datetime
        by_source = stats.get("by_source", {})

        lines = [
            f"TrendsCollector Summary ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
            f"Total items collected (24h): {stats.get('total', 0)}",
        ]

        if by_source:
            lines.append("")
            for src, cnt in sorted(by_source.items(), key=lambda x: -x[1]):
                lines.append(f"  {src}: {cnt}")

        if self._storage:
            lines.extend(["", "Top items by source:"])
            for src in sorted(by_source.keys()):
                items = self._storage.get_recent(source=src, limit=5, hours=24)
                if items:
                    source_label = {
                        "google_trends": "Google Trends",
                        "hackernews": "HN",
                        "github": "GitHub",
                        "wikipedia": "Wiki",
                        "youtube": "YT",
                    }.get(src, src)
                    for item in items:
                        title = item.get("title", "")[:60]

        return "\n".join(lines)
