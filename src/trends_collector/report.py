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
    by_source = stats.get("by_source", {})

    lines = [
        f"{'=' * 60}",
        f"\U0001f4ca \u70ed\u70b9\u91c7\u96c6\u65e5\u62a5 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]",
        f"{'=' * 60}",
        "",
    ]

    # ---- 统计概览 ----
    lines.append("\U0001f4c8 \u5404\u6e90\u7edf\u8ba1\uff0824h\uff09:")
    if by_source:
        for src, cnt in sorted(by_source.items(), key=lambda x: -x[1]):
            lines.append(f"  {src:30s}: {cnt:4d}")
    else:
        lines.append("  (no data)")
    lines.append("")

    # ---- 每个数据源取前 10 条 ----
    has_any = False
    for src in sorted(by_source.keys()):
        top_items = storage.get_recent(source=src, limit=10, hours=24)
        if not top_items:
            continue
        has_any = True

        source_label = {
            "google_trends": "Google Trends \u70ed\u641c",
            "reddit": "Reddit \u70ed\u5e16",
            "hackernews": "Hacker News \u524d\u9875",
            "github": "GitHub \u8d8b\u52bf\u4ed3\u5e93",
            "wikipedia": "Wikipedia \u6700\u4f73\u6587\u7ae0",
            "youtube": "YouTube \u70ed\u95e8\u89c6\u9891",
        }.get(src, src)

        lines.append(f"\U0001f525 [{source_label}] TOP 10:")
        for i, item in enumerate(top_items, 1):
            title = item.get("title", "")[:70]
            score = item.get("score", 0)
            url = item.get("url", "")
            region = item.get("region", "")
            tag = f" ({region})" if region and region not in src else ""

            score_str = ""
            if src == "google_trends" and score > 0:
                if score >= 1000000:
                    score_str = f" [ {score // 1000000}M+ ]"
                elif score >= 1000:
                    score_str = f" [ {score // 1000}K+ ]"
                else:
                    score_str = f" [ {score} ]"
            elif score > 0:
                score_str = f" (score: {score:,})"

            lines.append(f"  {i:2d}.{score_str}{tag} {title}")
            if url:
                lines.append(f"       {url}")
        lines.append("")

    if not has_any:
        lines.append("  (no trending data in past 24 hours)")
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
