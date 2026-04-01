"""Browser profile path definitions for all supported browsers."""

from __future__ import annotations

import os
from pathlib import Path

_LOCAL = os.environ.get("LOCALAPPDATA", "")
_ROAMING = os.environ.get("APPDATA", "")


def _p(*parts: str) -> Path:
    return Path(os.path.expandvars(os.path.join(*parts)))


# Each browser maps to a dict of { data_type: list_of_paths }
# Paths are relative to the browser's profile directory.
# For Chromium-based browsers the profile is "Default" (or "Profile 1" etc.)
# For Firefox it's a glob: Profiles/*.default-release

BROWSER_PROFILES: dict[str, dict[str, list[Path]]] = {
    "Chrome": {
        "base": [_p(_LOCAL, "Google", "Chrome", "User Data")],
        "cache": ["Default\\Cache", "Default\\Code Cache", "Default\\GPUCache"],
        "cookies": ["Default\\Cookies"],
        "history": ["Default\\History", "Default\\Visited Links"],
        "form_data": ["Default\\Web Data"],
        "sessions": ["Default\\Sessions"],
        "process_name": "chrome.exe",
    },
    "Edge": {
        "base": [_p(_LOCAL, "Microsoft", "Edge", "User Data")],
        "cache": ["Default\\Cache", "Default\\Code Cache", "Default\\GPUCache"],
        "cookies": ["Default\\Cookies"],
        "history": ["Default\\History", "Default\\Visited Links"],
        "form_data": ["Default\\Web Data"],
        "sessions": ["Default\\Sessions"],
        "process_name": "msedge.exe",
    },
    "Brave": {
        "base": [_p(_LOCAL, "BraveSoftware", "Brave-Browser", "User Data")],
        "cache": ["Default\\Cache", "Default\\Code Cache", "Default\\GPUCache"],
        "cookies": ["Default\\Cookies"],
        "history": ["Default\\History", "Default\\Visited Links"],
        "form_data": ["Default\\Web Data"],
        "sessions": ["Default\\Sessions"],
        "process_name": "brave.exe",
    },
    "Opera": {
        "base": [_p(_ROAMING, "Opera Software", "Opera Stable")],
        "cache": ["Cache", "Code Cache", "GPUCache"],
        "cookies": ["Cookies"],
        "history": ["History", "Visited Links"],
        "form_data": ["Web Data"],
        "sessions": ["Sessions"],
        "process_name": "opera.exe",
    },
    "Opera GX": {
        "base": [_p(_ROAMING, "Opera Software", "Opera GX Stable")],
        "cache": ["Cache", "Code Cache", "GPUCache"],
        "cookies": ["Cookies"],
        "history": ["History", "Visited Links"],
        "form_data": ["Web Data"],
        "sessions": ["Sessions"],
        "process_name": "opera.exe",
    },
    "Vivaldi": {
        "base": [_p(_LOCAL, "Vivaldi", "User Data")],
        "cache": ["Default\\Cache", "Default\\Code Cache", "Default\\GPUCache"],
        "cookies": ["Default\\Cookies"],
        "history": ["Default\\History", "Default\\Visited Links"],
        "form_data": ["Default\\Web Data"],
        "sessions": ["Default\\Sessions"],
        "process_name": "vivaldi.exe",
    },
    "Firefox": {
        # Firefox uses a different layout; paths resolved at runtime via glob
        "base": [_p(_ROAMING, "Mozilla", "Firefox", "Profiles")],
        "cache_base": [_p(_LOCAL, "Mozilla", "Firefox", "Profiles")],
        "cache": ["cache2"],
        "cookies": ["cookies.sqlite"],
        "history": ["places.sqlite"],
        "form_data": ["formhistory.sqlite"],
        "sessions": ["sessionstore-backups"],
        "process_name": "firefox.exe",
    },
}


def get_browser_paths(browser: str, data_type: str) -> list[Path]:
    """Return resolved absolute paths for a browser's data type.

    Returns only paths that exist on disk.
    """
    profile = BROWSER_PROFILES.get(browser)
    if not profile:
        return []

    results: list[Path] = []

    if browser == "Firefox":
        base_dirs = profile["base"]
        cache_dirs = profile.get("cache_base", profile["base"])
        rel_paths = profile.get(data_type, [])

        # Firefox profiles are subdirs of the base matching *.default*
        for base in base_dirs:
            if not base.exists():
                continue
            for prof_dir in base.iterdir():
                if prof_dir.is_dir():
                    for rel in rel_paths:
                        p = prof_dir / rel
                        if p.exists():
                            results.append(p)

        if data_type == "cache":
            for base in cache_dirs:
                if not base.exists():
                    continue
                for prof_dir in base.iterdir():
                    if prof_dir.is_dir():
                        for rel in rel_paths:
                            p = prof_dir / rel
                            if p.exists():
                                results.append(p)
    else:
        base_dirs = profile.get("base", [])
        rel_paths = profile.get(data_type, [])
        for base in base_dirs:
            if not base.exists():
                continue
            for rel in rel_paths:
                p = base / rel
                if p.exists():
                    results.append(p)

    return results


def installed_browsers() -> list[str]:
    """Return list of browsers that have a profile directory on this machine."""
    found = []
    for name, profile in BROWSER_PROFILES.items():
        for base in profile.get("base", []):
            if base.exists():
                found.append(name)
                break
    return found
