"""
Daily report generation.
Generates a human-readable report from stored trend data.
"""

import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Google Trends 国家代码 → 中文名
_GT_REGION_NAMES = {
    "US": "🇺🇸 美国",
    "GB": "🇬🇧 英国",
    "JP": "🇯🇵 日本",
    "KR": "🇰🇷 韩国",
    "CA": "🇨🇦 加拿大",
    "AU": "🇦🇺 澳大利亚",
    "DE": "🇩🇪 德国",
    "FR": "🇫🇷 法国",
    "BR": "🇧🇷 巴西",
    "IN": "🇮🇳 印度",
}

# Wikipedia 语言代码 → 中文名
_WP_LANG_NAMES = {
    "en": "🇬🇧 英文",
    "ja": "🇯🇵 日文",
    "ko": "🇰🇷 韩文",
    "de": "🇩🇪 德文",
    "fr": "🇫🇷 法文",
    "es": "🇪🇸 西班牙文",
    "pt": "🇧🇷 葡萄牙文",
}


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
            label = {
                "google_trends": "Google Trends",
                "reddit": "Reddit",
                "hackernews": "Hacker News",
                "github": "GitHub",
                "wikipedia": "Wikipedia",
                "youtube": "YouTube",
            }.get(src, src)
            lines.append(f"  {label:20s}: {cnt:4d}")
    else:
        lines.append("  (no data)")
    lines.append("")

    # ---- 每个数据源 ----
    has_any = False
    for src in sorted(by_source.keys()):
        if src == "google_trends":
            has_any |= _render_gt(storage, lines)
        elif src == "wikipedia":
            has_any |= _render_wp(storage, lines)
        else:
            has_any |= _render_other(src, storage, lines)

    if not has_any:
        lines.append("  (no trending data in past 24 hours)")
        lines.append("")

    lines.append(f"{'=' * 60}")
    return "\n".join(lines)


def _render_gt(storage, lines) -> bool:
    """Google Trends: 按国家分组，每个国家 TOP 10"""
    items = storage.get_recent(source="google_trends", limit=300, hours=24)
    if not items:
        return False

    groups = {}
    for item in items:
        r = item.get("region", "??")
        groups.setdefault(r, []).append(item)

    has = False
    for geo in sorted(groups.keys()):
        name = _GT_REGION_NAMES.get(geo, geo)
        top = groups[geo][:10]
        if not top:
            continue
        has = True
        lines.append(f"\U0001f525 [Google Trends - {name}] TOP 10:")
        for i, item in enumerate(top, 1):
            title = item.get("title", "")[:70]
            url = item.get("url", "")
            lines.append(f"  {i:2d}. {title}")
            if url:
                lines.append(f"       {url}")
        lines.append("")

    return has


def _render_wp(storage, lines) -> bool:
    """Wikipedia: 按语言分组，每种语言 TOP 10"""
    items = storage.get_recent(source="wikipedia", limit=300, hours=24)
    if not items:
        return False

    groups = {}
    for item in items:
        r = item.get("region", "??")
        groups.setdefault(r, []).append(item)

    has = False
    for lang in sorted(groups.keys()):
        name = _WP_LANG_NAMES.get(lang, lang)
        top = groups[lang][:10]
        if not top:
            continue
        has = True
        lines.append(f"\U0001f525 [Wikipedia - {name}] TOP 10:")
        for i, item in enumerate(top, 1):
            title = item.get("title", "")[:70]
            url = item.get("url", "")
            lines.append(f"  {i:2d}. {title}")
            if url:
                lines.append(f"       {url}")
        lines.append("")

    return has


def _render_other(src: str, storage, lines) -> bool:
    """其他源：整体 TOP 10，不再显示评分"""
    top_items = storage.get_recent(source=src, limit=10, hours=24)
    if not top_items:
        return False

    source_label = {
        "hackernews": "Hacker News 前页",
        "github": "GitHub 趋势仓库",
        "reddit": "Reddit 热门帖子",
        "youtube": "YouTube 热门视频",
    }.get(src, src)

    lines.append(f"\U0001f525 [{source_label}] TOP 10:")
    for i, item in enumerate(top_items, 1):
        title = item.get("title", "")[:70]
        url = item.get("url", "")
        lines.append(f"  {i:2d}. {title}")
        if url:
            lines.append(f"       {url}")
    lines.append("")

    return True


# -------- 外部接口 ----------

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
