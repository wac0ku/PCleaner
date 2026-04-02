"""Cleaning engine — executes deletion of discovered CleanItems."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pcleaner.core.scanner import CleanItem, ScanResult
from pcleaner.utils.elevation import is_admin
from pcleaner.utils.format import fmt_size
from pcleaner.utils.logger import log
from pcleaner.utils.security import run_safe, run_powershell


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class CleanResult:
    cleaned: list[CleanItem] = field(default_factory=list)
    skipped: list[CleanItem] = field(default_factory=list)
    errors: list[tuple[CleanItem, str]] = field(default_factory=list)

    @property
    def freed_bytes(self) -> int:
        return sum(i.size for i in self.cleaned)

    @property
    def freed_str(self) -> str:
        return fmt_size(self.freed_bytes)


# ---------------------------------------------------------------------------
# Special-case cleaners
# ---------------------------------------------------------------------------

def _clean_recycle_bin() -> None:
    run_powershell("Clear-RecycleBin -Force -ErrorAction SilentlyContinue", timeout=30)


def _flush_dns() -> None:
    run_safe(["ipconfig", "/flushdns"], timeout=10)


def _clear_clipboard() -> None:
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.CloseClipboard()
    except Exception:
        run_powershell("Set-Clipboard -Value $null", timeout=5)


# ---------------------------------------------------------------------------
# Core deletion helpers
# ---------------------------------------------------------------------------

def _delete_path(path: Path) -> bool:
    """Delete a file or directory. Returns True on success."""
    try:
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            # Delete contents but keep the directory itself
            for child in path.iterdir():
                try:
                    if child.is_file() or child.is_symlink():
                        child.unlink(missing_ok=True)
                    elif child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                except (PermissionError, OSError) as e:
                    log.debug("Could not delete %s: %s", child, e)
        return True
    except (PermissionError, OSError) as e:
        log.warning("Delete failed for %s: %s", path, e)
        return False


# ---------------------------------------------------------------------------
# Cleaner class
# ---------------------------------------------------------------------------

class Cleaner:
    """Executes cleanup based on a ScanResult."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._progress_cb: Callable[[CleanItem, int, int], None] | None = None

    def set_progress_callback(self, cb: Callable[[CleanItem, int, int], None]) -> None:
        """cb(item, current, total)"""
        self._progress_cb = cb

    def clean(self, scan_result: ScanResult) -> CleanResult:
        """Clean all enabled items from a scan result."""
        items = [i for i in scan_result.items if i.enabled]
        return self._clean_items(items)

    def clean_items(self, items: list[CleanItem]) -> CleanResult:
        return self._clean_items(items)

    def _clean_items(self, items: list[CleanItem]) -> CleanResult:
        result = CleanResult()
        total = len(items)
        admin = is_admin()

        for idx, item in enumerate(items):
            if self._progress_cb:
                self._progress_cb(item, idx + 1, total)

            # Skip admin-required items if not elevated
            if item.requires_admin and not admin:
                log.info("Skipping %s (requires admin)", item.path)
                result.skipped.append(item)
                continue

            if self.dry_run:
                result.cleaned.append(item)
                continue

            # Special-case handlers
            if item.category == "Recycle Bin":
                _clean_recycle_bin()
                result.cleaned.append(item)
                continue


            ok = _delete_path(item.path)
            if ok:
                result.cleaned.append(item)
            else:
                result.errors.append((item, f"Failed to delete {item.path}"))

        return result

    def flush_dns(self) -> bool:
        if self.dry_run:
            return True
        try:
            _flush_dns()
            return True
        except Exception as e:
            log.warning("DNS flush failed: %s", e)
            return False

    def clear_clipboard(self) -> bool:
        if self.dry_run:
            return True
        try:
            _clear_clipboard()
            return True
        except Exception as e:
            log.warning("Clipboard clear failed: %s", e)
            return False

    def empty_recycle_bin(self) -> bool:
        if self.dry_run:
            return True
        try:
            _clean_recycle_bin()
            return True
        except Exception as e:
            log.warning("Recycle bin empty failed: %s", e)
            return False
