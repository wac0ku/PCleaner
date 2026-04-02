"""Scanning engine — discovers junk files and returns CleanItem objects."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

from pcleaner.core.browsers import get_browser_paths, installed_browsers
from pcleaner.utils.config import cfg
from pcleaner.utils.format import fmt_size
from pcleaner.utils.logger import log
from pcleaner.utils.security import run_safe

_WIN = os.environ.get("WINDIR", r"C:\Windows")
_TEMP = os.environ.get("TEMP", str(Path.home() / "AppData" / "Local" / "Temp"))
_LOCAL = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
_ROAMING = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CleanItem:
    category: str          # e.g. "Temp Files"
    subcategory: str       # e.g. "System Temp"
    path: Path
    size: int = 0          # bytes
    description: str = ""
    safe: bool = True      # False = warn before deleting
    requires_admin: bool = False
    enabled: bool = True   # user can toggle per-item

    @property
    def size_str(self) -> str:
        return fmt_size(self.size)


@dataclass
class ScanResult:
    items: list[CleanItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return sum(i.size for i in self.items if i.enabled)

    @property
    def total_size_str(self) -> str:
        return fmt_size(self.total_size)

    @property
    def item_count(self) -> int:
        return len(self.items)

    def by_category(self) -> dict[str, list[CleanItem]]:
        result: dict[str, list[CleanItem]] = {}
        for item in self.items:
            result.setdefault(item.category, []).append(item)
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += _dir_size(Path(entry.path))
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    return total


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _collect_dir(path: Path) -> Iterator[Path]:
    """Yield one CleanItem per FILE inside path (recursively)."""
    try:
        for entry in os.scandir(path):
            try:
                p = Path(entry.path)
                if entry.is_file(follow_symlinks=False):
                    yield p
                elif entry.is_dir(follow_symlinks=False):
                    yield from _collect_dir(p)
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass


# ---------------------------------------------------------------------------
# Category scanners
# ---------------------------------------------------------------------------

def _scan_temp_files() -> list[CleanItem]:
    items: list[CleanItem] = []
    dirs = [
        (Path(_TEMP), "User Temp", False),
        (Path(_WIN, "Temp"), "Windows Temp", True),
        (Path(_LOCAL, "Temp"), "LocalAppData Temp", False),
    ]
    for d, sub, admin in dirs:
        if d.exists():
            sz = _dir_size(d)
            if sz > 0:
                items.append(CleanItem(
                    category="Temp Files",
                    subcategory=sub,
                    path=d,
                    size=sz,
                    description=f"Temporary files in {d}",
                    requires_admin=admin,
                ))
    return items


def _scan_system_cache() -> list[CleanItem]:
    items: list[CleanItem] = []

    # Prefetch
    prefetch = Path(_WIN, "Prefetch")
    if prefetch.exists():
        sz = _dir_size(prefetch)
        if sz > 0:
            items.append(CleanItem(
                category="System Cache",
                subcategory="Prefetch",
                path=prefetch,
                size=sz,
                description="Windows Prefetch files (speeds up app launches; safe to delete)",
                requires_admin=True,
            ))

    # Thumbnail cache
    thumb_dir = Path(_LOCAL, "Microsoft", "Windows", "Explorer")
    if thumb_dir.exists():
        for f in thumb_dir.glob("thumbcache_*.db"):
            sz = _file_size(f)
            if sz > 0:
                items.append(CleanItem(
                    category="System Cache",
                    subcategory="Thumbnail Cache",
                    path=f,
                    size=sz,
                    description="Windows thumbnail image cache",
                ))

    # Icon cache
    icon_cache = Path(_LOCAL, "IconCache.db")
    if icon_cache.exists():
        items.append(CleanItem(
            category="System Cache",
            subcategory="Icon Cache",
            path=icon_cache,
            size=_file_size(icon_cache),
            description="Windows icon cache database",
        ))

    return items


def _scan_windows_update() -> list[CleanItem]:
    items: list[CleanItem] = []
    wu_dir = Path(_WIN, "SoftwareDistribution", "Download")
    if wu_dir.exists():
        sz = _dir_size(wu_dir)
        if sz > 0:
            items.append(CleanItem(
                category="Windows Update",
                subcategory="Update Downloads",
                path=wu_dir,
                size=sz,
                description="Downloaded Windows Update files (already installed)",
                requires_admin=True,
            ))
    return items


def _scan_memory_dumps() -> list[CleanItem]:
    items: list[CleanItem] = []
    minidump = Path(_WIN, "Minidump")
    if minidump.exists():
        sz = _dir_size(minidump)
        if sz > 0:
            items.append(CleanItem(
                category="Memory Dumps",
                subcategory="Minidumps",
                path=minidump,
                size=sz,
                description="Windows crash minidump files",
                requires_admin=True,
            ))

    full_dump = Path(r"C:\Windows\MEMORY.DMP")
    if full_dump.exists():
        items.append(CleanItem(
            category="Memory Dumps",
            subcategory="Full Memory Dump",
            path=full_dump,
            size=_file_size(full_dump),
            description="Full Windows memory dump",
            requires_admin=True,
        ))
    return items


def _scan_log_files() -> list[CleanItem]:
    items: list[CleanItem] = []
    log_dirs = [
        (Path(_WIN, "Logs"), "Windows Logs", True),
        (Path(_LOCAL, "Microsoft", "Windows", "WER"), "Error Reports", False),
        (Path(_LOCAL, "CrashDumps"), "Crash Dumps", False),
        (Path(_TEMP), None, False),  # .log files in TEMP
    ]
    for d, sub, admin in log_dirs:
        if d.exists() and sub is not None:
            sz = _dir_size(d)
            if sz > 0:
                items.append(CleanItem(
                    category="Log Files",
                    subcategory=sub,
                    path=d,
                    size=sz,
                    description=f"Log files in {d}",
                    requires_admin=admin,
                ))
    return items


def _scan_recent_files() -> list[CleanItem]:
    items: list[CleanItem] = []
    recent = Path(_ROAMING, "Microsoft", "Windows", "Recent")
    if recent.exists():
        sz = _dir_size(recent)
        if sz > 0:
            items.append(CleanItem(
                category="Recent Files",
                subcategory="Recent File List",
                path=recent,
                size=sz,
                description="Windows recent documents list (shortcuts only, no actual files deleted)",
                safe=True,
                enabled=cfg.get("scan_categories.recent_files", False),
            ))
    return items


def _scan_recycle_bin() -> list[CleanItem]:
    items: list[CleanItem] = []
    # Estimate size via PowerShell
    try:
        result = run_safe(
            ["powershell", "-NoProfile", "-Command",
             "(New-Object -ComObject Shell.Application).Namespace(10).Items() | "
             "Measure-Object -Property Size -Sum | Select-Object -ExpandProperty Sum"],
            timeout=10,
        )
        sz = int(result.stdout.strip() or "0")
    except Exception:
        sz = 0
    items.append(CleanItem(
        category="Recycle Bin",
        subcategory="Recycle Bin",
        path=Path("$Recycle.Bin"),
        size=sz,
        description="Files in the Windows Recycle Bin",
    ))
    return items


def _scan_browser_data() -> list[CleanItem]:
    items: list[CleanItem] = []
    scan_cfg = cfg.get("scan_categories.browsers", {})

    for browser in installed_browsers():
        browser_cfg = scan_cfg.get(browser, {})
        for data_type in ("cache", "cookies", "history", "form_data", "sessions"):
            if not browser_cfg.get(data_type, data_type == "cache"):
                continue
            paths = get_browser_paths(browser, data_type)
            for p in paths:
                if p.is_dir():
                    sz = _dir_size(p)
                elif p.is_file():
                    sz = _file_size(p)
                else:
                    continue
                if sz > 0:
                    label = data_type.replace("_", " ").title()
                    items.append(CleanItem(
                        category="Browser Data",
                        subcategory=f"{browser} {label}",
                        path=p,
                        size=sz,
                        description=f"{browser} {label}",
                        safe=data_type not in ("cookies",),
                    ))
    return items


# ---------------------------------------------------------------------------
# Main Scanner class
# ---------------------------------------------------------------------------

CATEGORY_SCANNERS: dict[str, Callable[[], list[CleanItem]]] = {
    "temp_files":     _scan_temp_files,
    "system_cache":   _scan_system_cache,
    "windows_update": _scan_windows_update,
    "memory_dumps":   _scan_memory_dumps,
    "log_files":      _scan_log_files,
    "recent_files":   _scan_recent_files,
    "recycle_bin":    _scan_recycle_bin,
    "browsers":       _scan_browser_data,
}

CATEGORY_LABELS: dict[str, str] = {
    "temp_files":     "Temp Files",
    "system_cache":   "System Cache",
    "windows_update": "Windows Update Cache",
    "memory_dumps":   "Memory Dumps",
    "log_files":      "Log Files",
    "recent_files":   "Recent Files",
    "recycle_bin":    "Recycle Bin",
    "browsers":       "Browser Data",
}


class Scanner:
    """Parallel scan engine. Calls per-category scanners in a thread pool."""

    def __init__(self) -> None:
        self._result = ScanResult()
        self._progress_cb: Callable[[str, int, int], None] | None = None

    def set_progress_callback(self, cb: Callable[[str, int, int], None]) -> None:
        """cb(category_label, current, total)"""
        self._progress_cb = cb

    def scan_all(self, categories: list[str] | None = None) -> ScanResult:
        """Run all (or selected) category scanners in parallel."""
        to_scan = categories or list(CATEGORY_SCANNERS.keys())
        # Filter by config
        scan_cfg = cfg.get("scan_categories", {})
        enabled = [c for c in to_scan if scan_cfg.get(c, True)]

        result = ScanResult()
        total = len(enabled)

        workers = min(os.cpu_count() or 4, max(total, 1))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(CATEGORY_SCANNERS[cat]): cat for cat in enabled}
            done = 0
            for future in as_completed(futures):
                cat = futures[future]
                done += 1
                label = CATEGORY_LABELS.get(cat, cat)
                if self._progress_cb:
                    self._progress_cb(label, done, total)
                try:
                    items = future.result()
                    result.items.extend(items)
                except Exception as exc:
                    log.warning("Scanner error in %s: %s", cat, exc)
                    result.errors.append(f"{label}: {exc}")

        self._result = result
        return result

    def scan_category(self, category: str) -> list[CleanItem]:
        scanner = CATEGORY_SCANNERS.get(category)
        if not scanner:
            return []
        return scanner()

    @property
    def last_result(self) -> ScanResult:
        return self._result
