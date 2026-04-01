"""Persistent JSON configuration stored in %APPDATA%\\PCleaner\\config.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _config_dir() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    d = Path(appdata) / "PCleaner"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _backups_dir() -> Path:
    d = _config_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


CONFIG_PATH = _config_dir() / "config.json"
LOG_PATH = _config_dir() / "pcleaner.log"
BACKUPS_DIR = _backups_dir()

_DEFAULTS: dict[str, Any] = {
    "theme": "dark",
    "language": "en",
    "confirm_before_clean": True,
    "backup_registry": True,
    "wiper_passes": 3,
    "scan_categories": {
        "temp_files": True,
        "system_cache": True,
        "windows_update": True,
        "memory_dumps": True,
        "log_files": True,
        "recent_files": False,
        "recycle_bin": True,
        "dns_cache": True,
        "clipboard": False,
        "browsers": {
            "Chrome": {"cache": True, "cookies": False, "history": False, "form_data": False},
            "Edge":   {"cache": True, "cookies": False, "history": False, "form_data": False},
            "Firefox":{"cache": True, "cookies": False, "history": False, "form_data": False},
            "Brave":  {"cache": True, "cookies": False, "history": False, "form_data": False},
            "Opera":  {"cache": True, "cookies": False, "history": False, "form_data": False},
            "Vivaldi":{"cache": True, "cookies": False, "history": False, "form_data": False},
        },
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class Config:
    """Thread-safe JSON configuration manager."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if CONFIG_PATH.exists():
            try:
                with CONFIG_PATH.open("r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data = _deep_merge(_DEFAULTS, saved)
            except (json.JSONDecodeError, OSError):
                self._data = dict(_DEFAULTS)
        else:
            self._data = dict(_DEFAULTS)

    def save(self) -> None:
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        val: Any = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, default)
            else:
                return default
        return val

    def set(self, key: str, value: Any) -> None:
        keys = key.split(".")
        d = self._data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
        self.save()

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)


# Singleton
cfg = Config()
