"""
Email Relay HTTP Server for VPS A.
Receives reports from VPS B via HTTP POST and sends them via SMTP.

Runs as a standalone systemd service on VPS A.

Usage:
    python -m trends_collector.email_relay --port 8766 --config /path/to/config.yaml
"""

import sys
import json
import hmac
import logging
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from .config import load_config
from .notifier import _EmailChannel

logger = logging.getLogger("email_relay")


class RelayHandler(BaseHTTPRequestHandler):
    email_channel: _EmailChannel = None
    push_key: str = ""

    def do_POST(self):
        if self.path != "/send":
            self._respond(404, {"error": "not found"})
            return

        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            self._respond(400, {"error": "empty body"})
            return

        try:
            body = json.loads(self.rfile.read(content_len))
        except Exception:
            self._respond(400, {"error": "invalid JSON"})
            return

        # Auth check
        if self.push_key:
            provided = body.get("key", "")
            if not hmac.compare_digest(provided, self.push_key):
                self._respond(403, {"error": "invalid key"})
                return

        text = body.get("text", "")
        subject = body.get("subject", "TrendsCollector Report")

        if not text:
            self._respond(400, {"error": "empty text"})
            return

        self.email_channel.send(text, subject)
        self._respond(200, {"ok": True})

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        logger.info(f"{self.client_address[0]} - {fmt % args}")


def main():
    parser = argparse.ArgumentParser(description="TrendsCollector Email Relay")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--config", type=str, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    notif_cfg = config.get("notifications", {})
    email_channel = _EmailChannel(notif_cfg)

    if not email_channel.enabled:
        print("ERROR: Email channel is not enabled in config.yaml")
        print("       Set notifications.email.enabled: true and configure SMTP.")
        sys.exit(1)

    # Read push_key from relay config or env
    push_key = config.get("relay", {}).get("push_key", "")
    if not push_key:
        import os
        push_key = os.environ.get("RELAY_PUSH_KEY", "")

    RelayHandler.email_channel = email_channel
    RelayHandler.push_key = push_key

    server = HTTPServer(("0.0.0.0", args.port), RelayHandler)
    logger.info(f"Email relay listening on 0.0.0.0:{args.port}")

    if push_key:
        logger.info("Push key authentication enabled")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        logger.info("Relay stopped")


if __name__ == "__main__":
    main()
