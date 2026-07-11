"""
Lightweight HTTP receiver for China relay collector.
Runs as a separate systemd service on the overseas VPS.

Accepts POST /collect from the China-side relay script,
validates the auth key, and saves items into the main SQLite database.

Usage:
    python -m trends_collector.receiver [--port 8765] [--config /path/to/config.yaml]
"""

import sys
import json
import hmac
import logging
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Add project src to path so we can import trends_collector modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from trends_collector.config import load_config
from trends_collector.storage import Storage
from trends_collector.notifier import Notifier

logger = logging.getLogger("receiver")


class CollectHandler(BaseHTTPRequestHandler):
    storage: Storage = None
    push_key: str = ""
    notifier: Notifier = None

    def do_POST(self):
        if self.path != "/collect":
            self.send_error(404)
            return

        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            self._respond(400, "empty body")
            return

        try:
            body = json.loads(self.rfile.read(content_len))
        except Exception:
            self._respond(400, "invalid JSON")
            return

        # Auth check
        provided_key = body.get("key", "")
        if not hmac.compare_digest(provided_key, self.push_key):
            self._respond(403, "invalid key")
            return

        items = body.get("items", [])
        if not items:
            self._respond(200, {"saved": 0})

        collected_at = body.get("collected_at", "")
        new_count = 0
        for item in items:
            ok = self.storage.save(
                source=item.get("source", "china_relay"),
                title=item.get("title", ""),
                url=item.get("url", ""),
                rank=item.get("rank", 0),
                score=item.get("score", 0),
                region=item.get("region", "CN"),
                ip=self.client_address[0],
                raw_data=json.dumps(item, ensure_ascii=False),
            )
            if ok:
                new_count += 1

        logger.info(f"Received {len(items)} items from relay, saved {new_count} new")
        self._respond(200, {"received": len(items), "saved": new_count})

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self.send_error(404)

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
    parser = argparse.ArgumentParser(description="TrendsCollector Relay Receiver")
    parser.add_argument("--port", type=int, default=8765, help="Listen port")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    storage = Storage(config["storage"]["db_path"])

    # Read push_key from config or env
    push_key = config.get("relay", {}).get("push_key", "") or ""
    if not push_key:
        import os
        push_key = os.environ.get("RELAY_PUSH_KEY", "")

    if not push_key:
        print("ERROR: relay.push_key not set in config.yaml and RELAY_PUSH_KEY not set in env")
        sys.exit(1)

    # Setup logging
    log_dir = Path(config.get("log_dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")
    fh = logging.FileHandler(log_dir / "receiver.log", encoding="utf-8")
    fh.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(fh)
    root.addHandler(logging.StreamHandler(sys.stdout))

    CollectHandler.storage = storage
    CollectHandler.push_key = push_key
    CollectHandler.notifier = Notifier(config)

    server = HTTPServer(("0.0.0.0", args.port), CollectHandler)
    logger.info(f"Receiver listening on 0.0.0.0:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        logger.info("Receiver stopped")


if __name__ == "__main__":
    main()
