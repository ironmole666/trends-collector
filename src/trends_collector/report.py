"""
Daily report generation.
Generates a human-readable report from stored trend data.
"""

import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_daily_report(storage) -> str:
    """Generate the full daily report text."""
    stats = storage.get_stats(hours=24)
    top = storage.get_top(hours=24, limit=20)
    sources = storage.get_sources_summary()

    lines = [
        f"{'=' * 60}",
        f"\U0001f4ca \u70ed\u70b9\u91c7\u96c6\u65e5\u62a5 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]",
        f"{'=' * 60}",
        "",
    ]

    lines.append("\U0001f4c8 \u5404\u6e90\u7edf\u8ba1\uff0824h\uff09:")
    if stats.get("by_source"):
        for src, cnt in sorted(stats["by_source"].items(), key=lambda x: -x[1]):
            lines.append(f"  {src:30s}: {cnt:4d}")
    else:
        lines.append("  (no data)")

    lines.extend(["", "", "\U0001f525 \u70ed\u95e8\u5185\u5bb9 TOP 20:", ""])
    for i, item in enumerate(top, 1):
        title = item.get("title", "")[:70]
        score = item.get("score", 0)
        source = item.get("source", "")
        url = item.get("url", "")
        lines.append(f"  {i:2d}. [{source}] (score: {score})")
        lines.append(f"       {title}")
        if url:
            lines.append(f"       {url}")
        lines.append("")

    lines.append(f"{'=' * 60}")

    return "\n".join(lines)


def save_report(storage, log_dir: str) -> Path:
    """Save the report to a timestamped file in log_dir. Returns the file path."""
    report = generate_daily_report(storage)
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    filename = f"report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    filepath = log_path / filename
    filepath.write_text(report, encoding="utf-8")
    logger.info(f"Report saved to {filepath}")
    return filepath


def print_report(storage):
    """Print the report to stdout."""
    print(generate_daily_report(storage))
