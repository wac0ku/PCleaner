"""Startup manager — lists and controls programs that run at Windows boot."""

from __future__ import annotations

import subprocess
import winreg
from dataclasses import dataclass
from typing import Iterator

from pcleaner.utils.logger import log

_RUN_KEYS = [
    (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\Run",        "HKCU Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run",        "HKLM Run"),
    (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\RunOnce",    "HKCU RunOnce"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce",    "HKLM RunOnce"),
]
_DISABLED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"


@dataclass
class StartupEntry:
    name: str
    command: str
    source: str        # "HKCU Run", "HKLM Run", "Task Scheduler"
    enabled: bool
    hive: int | None = None   # winreg hive constant
    key_path: str = ""

    @property
    def type_icon(self) -> str:
        if "Task" in self.source:
            return "T"
        return "R"


def _enum_run_key(hive: int, path: str, source: str) -> Iterator[StartupEntry]:
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as key:
            idx = 0
            while True:
                try:
                    name, data, _ = winreg.EnumValue(key, idx)
                    yield StartupEntry(
                        name=name,
                        command=str(data),
                        source=source,
                        enabled=True,
                        hive=hive,
                        key_path=path,
                    )
                    idx += 1
                except OSError:
                    break
    except OSError:
        pass


def _get_scheduled_tasks() -> list[StartupEntry]:
    """Get startup tasks from Task Scheduler."""
    tasks: list[StartupEntry] = []
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/FO", "CSV", "/V"],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace"
        )
        lines = result.stdout.strip().splitlines()
        if len(lines) < 2:
            return tasks
        # Parse CSV-ish output
        for line in lines[1:]:
            parts = line.split('","')
            if len(parts) < 9:
                continue
            task_name = parts[0].strip('"')
            status = parts[3].strip('"') if len(parts) > 3 else ""
            run_at = parts[5].strip('"') if len(parts) > 5 else ""
            task_to_run = parts[8].strip('"') if len(parts) > 8 else ""
            if "logon" in run_at.lower() or "startup" in run_at.lower():
                tasks.append(StartupEntry(
                    name=task_name.split("\\")[-1],
                    command=task_to_run,
                    source="Task Scheduler",
                    enabled="Disabled" not in status,
                ))
    except Exception as e:
        log.debug("Task Scheduler query failed: %s", e)
    return tasks


class StartupManager:
    """Manages Windows startup programs."""

    def list_entries(self) -> list[StartupEntry]:
        entries: list[StartupEntry] = []
        for hive, path, source in _RUN_KEYS:
            entries.extend(_enum_run_key(hive, path, source))
        entries.extend(_get_scheduled_tasks())
        return entries

    def disable(self, entry: StartupEntry) -> bool:
        """Disable a startup entry by renaming its key under DisabledRun."""
        if entry.hive is None:
            return self._disable_task(entry.name)
        try:
            src_hive = entry.hive
            # Copy value to disabled key
            disabled_path = _DISABLED_KEY
            with winreg.OpenKey(src_hive, disabled_path, 0,
                                winreg.KEY_SET_VALUE | winreg.KEY_CREATE_SUB_KEY) as dst:
                winreg.SetValueEx(dst, entry.name, 0, winreg.REG_BINARY,
                                  b"\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
            # Delete from run key
            with winreg.OpenKey(src_hive, entry.key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, entry.name)
            log.info("Disabled startup: %s", entry.name)
            return True
        except OSError as e:
            log.warning("Failed to disable startup %s: %s", entry.name, e)
            return False

    def enable(self, entry: StartupEntry) -> bool:
        """Re-enable a disabled startup entry."""
        if entry.hive is None:
            return self._enable_task(entry.name)
        try:
            with winreg.OpenKey(entry.hive, entry.key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, entry.name, 0, winreg.REG_SZ, entry.command)
            log.info("Enabled startup: %s", entry.name)
            return True
        except OSError as e:
            log.warning("Failed to enable startup %s: %s", entry.name, e)
            return False

    def delete(self, entry: StartupEntry) -> bool:
        """Permanently remove a startup entry."""
        if entry.hive is None:
            return self._delete_task(entry.name)
        try:
            with winreg.OpenKey(entry.hive, entry.key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, entry.name)
            log.info("Deleted startup: %s", entry.name)
            return True
        except OSError as e:
            log.warning("Failed to delete startup %s: %s", entry.name, e)
            return False

    def _disable_task(self, name: str) -> bool:
        try:
            result = subprocess.run(
                ["schtasks", "/Change", "/TN", name, "/Disable"],
                capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _enable_task(self, name: str) -> bool:
        try:
            result = subprocess.run(
                ["schtasks", "/Change", "/TN", name, "/Enable"],
                capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _delete_task(self, name: str) -> bool:
        try:
            result = subprocess.run(
                ["schtasks", "/Delete", "/TN", name, "/F"],
                capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False
