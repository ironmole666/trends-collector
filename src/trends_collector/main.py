"""
TrendsCollector - Multi-source trending topics collector.

Usage:
    python -m trends_collector                  # Run continuously
    python -m trends_collector --report         # Print daily report and exit
    python -m trends_collector --once           # Run one cycle and exit
"""

import sys
import time
import random
import logging
import argparse
from pathlib import Path

import requests

from .config import load_config
from .storage import Storage
from .notifier import Notifier
from .report import print_report, save_report
from .collectors import (
    GoogleTrendsCollector,
    RedditCollector,
    HackerNewsCollector,
    YouTubeCollector,
    GitHubCollector,
    WikipediaCollector,
)

logger = logging.getLogger(__name__)


def setup_logging(log_dir, level="INFO"):
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # File handler
    fh = logging.FileHandler(log_path / "collector.log", encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    return log_path


def get_current_ip() -> str:
    try:
        return requests.get("https://api.ipify.org", timeout=10).text.strip()
    except Exception as e:
        logger.warning(f"Failed to get public IP: {e}")
        return "unknown"


def build_collectors(config: dict):
    collectors = []

    gt_cfg = config.get("collectors", {}).get("google_trends", {})
    if gt_cfg.get("enabled", True):
        collectors.append(GoogleTrendsCollector(gt_cfg))

    rd_cfg = config.get("collectors", {}).get("reddit", {})
    if rd_cfg.get("enabled", True):
        collectors.append(RedditCollector(rd_cfg))

    hn_cfg = config.get("collectors", {}).get("hackernews", {})
    if hn_cfg.get("enabled", True):
        collectors.append(HackerNewsCollector(hn_cfg))

    gh_cfg = config.get("collectors", {}).get("github", {})
    if gh_cfg.get("enabled", True):
        collectors.append(GitHubCollector(gh_cfg))

    wp_cfg = config.get("collectors", {}).get("wikipedia", {})
    if wp_cfg.get("enabled", True):
        collectors.append(WikipediaCollector(wp_cfg))

    yt_cfg = config.get("collectors", {}).get("youtube", {})
    if yt_cfg.get("enabled", False):
        col = YouTubeCollector(yt_cfg)
        if col.is_available():
            collectors.append(col)
        else:
            logger.warning("YouTube collector enabled but no API key set, skipping")

    return collectors


def run_collection(config: dict, storage: Storage, notifier: Notifier, log_dir: str):
    ip = get_current_ip()
    logger.info(f"=== Collection started [IP: {ip}] ===")

    collectors = build_collectors(config)
    total_new = 0
    total_items = 0

    for collector in collectors:
        collector.set_ip(ip)
        try:
            items = collector.collect()
            new_count = storage.batch_save(items)
            total_items += len(items)
            total_new += new_count
            logger.info(
                f"[{collector.source_name}] collected {len(items)}, new {new_count}"
            )
        except Exception as e:
            logger.error(f"[{collector.source_name}] collection failed: {e}")
            notifier.send_error(f"[{collector.source_name}] {e}")
        time.sleep(1)  # polite delay between sources

    logger.info(f"=== Collection done: {total_items} items, {total_new} new ===")

    # Save report to file
    report_path = save_report(storage, log_dir)
    logger.info(f"Report written to {report_path}")

    # Send summary notification
    stats = storage.get_stats(hours=24)
    top = storage.get_top(hours=24, limit=10)
    notifier.send_summary(stats, top)

    return total_new


def main():
    parser = argparse.ArgumentParser(description="TrendsCollector")
    parser.add_argument("--report", action="store_true", help="Print daily report and exit")
    parser.add_argument("--once", action="store_true", help="Run one collection cycle and exit")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")

    args = parser.parse_args()

    config = load_config(args.config)
    log_dir = setup_logging(
        config.get("log_dir", "logs"),
        config.get("log_level", "INFO"),
    )
    storage = Storage(config["storage"]["db_path"])
    notifier = Notifier(config)
    notifier.set_storage(storage)
    if args.report:
        print_report(storage)
        save_report(storage, log_dir)
        return

    if args.once:
        run_collection(config, storage, notifier, log_dir)
        return

    # Default: continuous mode with random delay between cycles
    delay_range = (25 * 60, 35 * 60)
    logger.info(f"Continuous mode: delay range {delay_range[0]//60}-{delay_range[1]//60} min")
    while True:
        run_collection(config, storage, notifier, log_dir)
        storage.enforce_retention(config.get("storage", {}).get("retention_days", 30))
        sleep_secs = random.randint(*delay_range)
        logger.info(f"Next collection in {sleep_secs // 60} minutes")
        time.sleep(sleep_secs)


if __name__ == "__main__":
    main()
