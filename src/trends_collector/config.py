"""
Configuration loader.
Loads config.yaml from default paths, merges with environment variables.
"""

import os
import yaml
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


def load_config(config_path=None):
    """Load configuration from YAML file, falling back to defaults."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    defaults = {
        "project": {"name": "trends-collector"},
        "data_dir": None,
        "log_dir": None,
        "log_level": "INFO",
        "collectors": {
            "google_trends": {
                "enabled": True,
                "regions": ["US", "GB", "JP", "KR", "CA", "AU", "DE", "FR"],
            },
            "reddit": {
                "enabled": True,
                "subreddits": ["all", "worldnews", "technology", "science"],
                "limit": 25,
            },
            "hackernews": {
                "enabled": True,
                "limit": 30,
            },
            "youtube": {
                "enabled": False,
                "api_key": "",
                "regions": ["US", "JP", "KR", "GB"],
            },
            "github": {
                "enabled": True,
                "languages": ["python", "javascript", "go", "rust", "typescript"],
            },
        },
        "storage": {
            "db_path": None,
            "retention_days": 30,
        },
        "notifications": {
            "telegram": {
                "enabled": False,
                "bot_token": "",
                "chat_id": "",
            },
            "email": {
                "enabled": False,
                "smtp_host": "",
                "smtp_port": 587,
                "smtp_user": "",
                "smtp_password": "",
                "smtp_use_tls": True,
                "from_addr": "",
                "to_addrs": [],
            },
        },
    }

    cfg = defaults.copy()

    if path.exists():
        with open(path, "r") as f:
            user_cfg = yaml.safe_load(f) or {}
        _deep_merge(cfg, user_cfg)

    # Resolve auto paths relative to project root
    project_root = path.parent if path.exists() else Path.cwd()

    if cfg.get("data_dir"):
        cfg["data_dir"] = Path(cfg["data_dir"])
    else:
        cfg["data_dir"] = project_root / "data"

    if cfg.get("log_dir"):
        cfg["log_dir"] = Path(cfg["log_dir"])
    else:
        cfg["log_dir"] = project_root / "logs"

    if not cfg["storage"].get("db_path"):
        cfg["storage"]["db_path"] = str(cfg["data_dir"] / "trends.db")

    # Override secrets from environment variables
    env_overrides = {
        ("collectors", "youtube", "api_key"): "YOUTUBE_API_KEY",
        ("notifications", "telegram", "bot_token"): "TELEGRAM_BOT_TOKEN",
        ("notifications", "telegram", "chat_id"): "TELEGRAM_CHAT_ID",
        ("notifications", "email", "smtp_password"): "EMAIL_SMTP_PASSWORD",
    }

    for keys, env_var in env_overrides.items():
        val = os.environ.get(env_var)
        if val:
            target = cfg
            for k in keys[:-1]:
                target = target.setdefault(k, {})
            target[keys[-1]] = val

    return cfg


def _deep_merge(base, override):
    """Recursively merge override into base dict."""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val
