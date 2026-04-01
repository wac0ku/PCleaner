"""Registry scanner and cleaner with automatic backup."""

from __future__ import annotations

import subprocess
import winreg
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

from pcleaner.utils.config import BACKUPS_DIR
from pcleaner.utils.logger import log


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RegistryIssue:
    hive: str          # "HKCU" or "HKLM"
    key_path: str      # e.g. "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
    value_name: str    # registry value name (empty string = default value)
    issue_type: str    # "MissingFile", "OrphanedKey", "InvalidPath", etc.
    description: str
    enabled: bool = True

    @property
    def full_path(self) -> str:
        return f"{self.hive}\\{self.key_path}"

    @property
    def display(self) -> str:
        if self.value_name:
            return f"{self.full_path} → {self.value_name}"
        return self.full_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HIVE_MAP = {
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKCR": winreg.HKEY_CLASSES_ROOT,
}


def _open_key(hive: str, path: str, write: bool = False):
    root = _HIVE_MAP.get(hive, winreg.HKEY_CURRENT_USER)
    access = winreg.KEY_READ | (winreg.KEY_SET_VALUE if write else 0)
    try:
        return winreg.OpenKey(root, path, 0, access)
    except OSError:
        return None


def _enum_values(key) -> Iterator[tuple[str, object, int]]:
    idx = 0
    while True:
        try:
            yield winreg.EnumValue(key, idx)
            idx += 1
        except OSError:
            break


def _enum_subkeys(key) -> Iterator[str]:
    idx = 0
    while True:
        try:
            yield winreg.EnumKey(key, idx)
            idx += 1
        except OSError:
            break


def _path_exists(raw: str) -> bool:
    """Check if a filesystem path extracted from a registry value exists."""
    if not raw:
        return True
    # Strip quotes and arguments
    raw = raw.strip().strip('"')
    # Take first token (the executable path)
    exe = raw.split('"')[0].split(" /")[0].split(" -")[0].strip()
    if not exe:
        return True
    # Expand environment variables
    try:
        import os
        expanded = os.path.expandvars(exe)
        return Path(expanded).exists()
    except Exception:
        return True  # Assume valid if we can't resolve


# ---------------------------------------------------------------------------
# Scanner checks
# ---------------------------------------------------------------------------

def _check_run_keys() -> list[RegistryIssue]:
    """Check HKCU and HKLM Run keys for entries pointing to missing files."""
    issues: list[RegistryIssue] = []
    locations = [
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run"),
        ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run"),
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    ]
    for hive, path in locations:
        key = _open_key(hive, path)
        if not key:
            continue
        try:
            for name, data, _ in _enum_values(key):
                if isinstance(data, str) and not _path_exists(data):
                    issues.append(RegistryIssue(
                        hive=hive,
                        key_path=path,
                        value_name=name,
                        issue_type="MissingFile",
                        description=f"Startup entry points to missing file: {data[:80]}",
                    ))
        finally:
            key.Close()
    return issues


def _check_uninstall_keys() -> list[RegistryIssue]:
    """Check uninstall entries with missing DisplayIcon or InstallLocation."""
    issues: list[RegistryIssue] = []
    locations = [
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, base in locations:
        base_key = _open_key(hive, base)
        if not base_key:
            continue
        try:
            for subkey_name in _enum_subkeys(base_key):
                sub = _open_key(hive, f"{base}\\{subkey_name}")
                if not sub:
                    continue
                try:
                    display_name = None
                    install_loc = None
                    uninstall_str = None
                    for name, data, _ in _enum_values(sub):
                        if name == "DisplayName":
                            display_name = data
                        elif name == "InstallLocation":
                            install_loc = data
                        elif name == "UninstallString":
                            uninstall_str = data
                    # Check if UninstallString path is missing
                    if uninstall_str and not _path_exists(uninstall_str):
                        label = display_name or subkey_name
                        issues.append(RegistryIssue(
                            hive=hive,
                            key_path=f"{base}\\{subkey_name}",
                            value_name="UninstallString",
                            issue_type="OrphanedUninstall",
                            description=f"Orphaned uninstall entry: {label}",
                        ))
                    # Check InstallLocation
                    elif install_loc and install_loc.strip() and not Path(install_loc.strip()).exists():
                        label = display_name or subkey_name
                        issues.append(RegistryIssue(
                            hive=hive,
                            key_path=f"{base}\\{subkey_name}",
                            value_name="InstallLocation",
                            issue_type="MissingInstallDir",
                            description=f"Install directory missing: {label}",
                        ))
                finally:
                    sub.Close()
        finally:
            base_key.Close()
    return issues


def _check_file_extensions() -> list[RegistryIssue]:
    """Check HKCU\\Software\\Classes for .ext pointing to missing handlers."""
    issues: list[RegistryIssue] = []
    base_key = _open_key("HKCU", r"Software\Classes")
    if not base_key:
        return issues
    try:
        for ext in _enum_subkeys(base_key):
            if not ext.startswith("."):
                continue
            sub = _open_key("HKCU", f"Software\\Classes\\{ext}")
            if not sub:
                continue
            try:
                # Read default value (the ProgID)
                try:
                    prog_id, _, _ = winreg.QueryValueEx(sub, "")
                except OSError:
                    prog_id = None
                if prog_id:
                    # Check if the ProgID key exists
                    handler = _open_key("HKCU", f"Software\\Classes\\{prog_id}")
                    if not handler:
                        # Also check HKCR
                        handler = _open_key("HKCR", prog_id)
                    if not handler:
                        issues.append(RegistryIssue(
                            hive="HKCU",
                            key_path=f"Software\\Classes\\{ext}",
                            value_name="",
                            issue_type="MissingProgID",
                            description=f"File extension {ext} points to missing handler: {prog_id}",
                        ))
                    else:
                        handler.Close()
            finally:
                sub.Close()
    finally:
        base_key.Close()
    return issues[:200]  # Cap at 200 to avoid excessive results


# ---------------------------------------------------------------------------
# Main classes
# ---------------------------------------------------------------------------

class RegistryScanner:
    """Scans the registry for issues."""

    def scan(self, progress_cb=None) -> list[RegistryIssue]:
        checks = [
            ("Startup Entries", _check_run_keys),
            ("Uninstall Keys", _check_uninstall_keys),
            ("File Extensions", _check_file_extensions),
        ]
        all_issues: list[RegistryIssue] = []
        for i, (label, fn) in enumerate(checks):
            if progress_cb:
                progress_cb(label, i + 1, len(checks))
            try:
                all_issues.extend(fn())
            except Exception as exc:
                log.warning("Registry check %s failed: %s", label, exc)
        return all_issues


class RegistryCleaner:
    """Backs up and cleans registry issues."""

    def backup(self, hive: str = "HKCU", sub_path: str = "") -> Path | None:
        """Export registry key to a .reg backup file."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUPS_DIR / f"registry_backup_{ts}.reg"
        key = f"{hive}\\{sub_path}" if sub_path else hive
        try:
            result = subprocess.run(
                ["reg", "export", key, str(backup_file), "/y"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                log.info("Registry backup saved to %s", backup_file)
                return backup_file
        except Exception as e:
            log.warning("Registry backup failed: %s", e)
        return None

    def backup_full(self) -> Path | None:
        """Backup all HKCU keys before any cleaning."""
        return self.backup("HKCU")

    def clean(self, issues: list[RegistryIssue], dry_run: bool = False) -> tuple[int, int]:
        """Delete registry values for the given issues. Returns (cleaned, errors)."""
        if not dry_run:
            self.backup_full()

        cleaned = 0
        errors = 0
        for issue in issues:
            if not issue.enabled:
                continue
            if dry_run:
                cleaned += 1
                continue
            root = _HIVE_MAP.get(issue.hive, winreg.HKEY_CURRENT_USER)
            try:
                if issue.value_name:
                    with winreg.OpenKey(root, issue.key_path, 0, winreg.KEY_SET_VALUE) as key:
                        winreg.DeleteValue(key, issue.value_name)
                else:
                    winreg.DeleteKey(root, issue.key_path)
                cleaned += 1
                log.info("Deleted registry: %s → %s", issue.key_path, issue.value_name)
            except OSError as e:
                log.warning("Failed to delete registry %s: %s", issue.full_path, e)
                errors += 1

        return cleaned, errors
