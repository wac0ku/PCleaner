"""Automated Task Manager — detects and manages suspicious processes."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import psutil

from pcleaner.utils.logger import log


# ---------------------------------------------------------------------------
# Known suspicious indicators
# ---------------------------------------------------------------------------

# Common malware / PUP process names (lowercase)
_SUSPICIOUS_NAMES: set[str] = {
    # Miners
    "xmrig", "minergate", "nicehash", "cpuminer", "bfgminer", "cgminer",
    "minerd", "ethminer", "claymore", "phoenixminer", "nbminer", "t-rex",
    # RATs / Backdoors
    "darkcomet", "njrat", "netbus", "subseven", "poisonivy", "blackshades",
    "quasar", "asyncrat", "remcos", "warzone", "nanocore", "orcus",
    # Adware / PUPs
    "bonzi", "ask toolbar", "conduit", "babylon", "opencandy", "installcore",
    "softpulse", "crossrider", "yontoo", "superfish",
    # Keyloggers
    "ardamax", "revealer", "spyrix", "kidlogger", "refog",
    # Generic suspicious
    "payload", "exploit", "backdoor", "trojan", "keylog", "rootkit",
    "cryptolocker", "ransomware", "botnet",
}

# High-risk path patterns — processes should almost never run from here
_HIGH_RISK_PATHS: list[str] = [
    "\\appdata\\local\\temp\\",
    "\\users\\public\\",
    "\\windows\\temp\\",
    "\\$recycle.bin\\",
]

# System-critical processes that should NEVER be killed
_PROTECTED_PROCESSES: set[str] = {
    "system", "system idle process", "registry", "smss.exe", "csrss.exe",
    "wininit.exe", "services.exe", "lsass.exe", "winlogon.exe",
    "svchost.exe", "dwm.exe", "explorer.exe", "taskhostw.exe",
    "runtimebroker.exe", "sihost.exe", "fontdrvhost.exe",
    "conhost.exe", "dllhost.exe", "searchhost.exe",
    "startmenuexperiencehost.exe", "textinputhost.exe",
    "shellexperiencehost.exe", "applicationframehost.exe",
    "securityhealthservice.exe", "securityhealthsystray.exe",
    "msmpeng.exe", "nissrv.exe",  # Windows Defender
    "spoolsv.exe", "wuauserv.exe", "audiodg.exe",
    "ctfmon.exe", "searchindexer.exe", "msdtc.exe",
    "lsaiso.exe", "sgrmbroker.exe", "memcompression",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SuspicionReason:
    """A single reason why a process is flagged."""
    category: str       # e.g. "high_cpu", "suspicious_name", "temp_path"
    description: str    # Human-readable explanation
    severity: str       # "low", "medium", "high", "critical"
    score: int          # 1-100 contribution to overall suspicion score


@dataclass
class ProcessEntry:
    """A running process with suspicion analysis."""
    pid: int
    name: str
    exe_path: str
    cmdline: str
    username: str
    cpu_percent: float
    memory_mb: float
    status: str
    create_time: float
    is_protected: bool = False
    suspicion_score: int = 0
    reasons: list[SuspicionReason] = field(default_factory=list)

    @property
    def severity(self) -> str:
        if self.suspicion_score >= 70:
            return "critical"
        if self.suspicion_score >= 50:
            return "high"
        if self.suspicion_score >= 30:
            return "medium"
        if self.suspicion_score > 0:
            return "low"
        return "clean"

    @property
    def severity_icon(self) -> str:
        icons = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🔵",
            "clean": "🟢",
        }
        return icons.get(self.severity, "⚪")

    @property
    def is_suspicious(self) -> bool:
        return self.suspicion_score > 0

    @property
    def reason_summary(self) -> str:
        if not self.reasons:
            return "Clean"
        return "; ".join(r.description for r in self.reasons[:3])


@dataclass
class TaskManagerResult:
    """Result of a process scan."""
    all_processes: list[ProcessEntry] = field(default_factory=list)
    suspicious: list[ProcessEntry] = field(default_factory=list)
    total_cpu: float = 0.0
    total_ram_mb: float = 0.0

    @property
    def suspicious_count(self) -> int:
        return len(self.suspicious)

    @property
    def critical_count(self) -> int:
        return sum(1 for p in self.suspicious if p.severity == "critical")

    @property
    def high_count(self) -> int:
        return sum(1 for p in self.suspicious if p.severity == "high")


# ---------------------------------------------------------------------------
# Task Manager
# ---------------------------------------------------------------------------

class TaskManager:
    """Scans running processes and flags suspicious ones."""

    def __init__(self) -> None:
        self._progress_cb: Callable[[str, int, int], None] | None = None

    def set_progress_callback(self, cb: Callable[[str, int, int], None]) -> None:
        self._progress_cb = cb

    def scan(self) -> TaskManagerResult:
        """Scan all running processes and analyze for suspicious behavior."""
        result = TaskManagerResult()
        entries: list[ProcessEntry] = []

        # First pass: collect CPU percentages (needs interval)
        try:
            psutil.cpu_percent(interval=0)  # prime
        except Exception:
            pass

        procs = list(psutil.process_iter([
            "pid", "name", "exe", "cmdline", "username",
            "cpu_percent", "memory_info", "status", "create_time",
        ]))
        total = len(procs)

        for i, proc in enumerate(procs):
            if self._progress_cb and i % 50 == 0:
                self._progress_cb("Scanning processes", i, total)

            try:
                info = proc.info
                name = info.get("name") or "?"
                exe_path = info.get("exe") or ""
                cmdline_parts = info.get("cmdline") or []
                cmdline = " ".join(cmdline_parts) if cmdline_parts else ""
                username = info.get("username") or ""
                cpu_pct = info.get("cpu_percent") or 0.0
                mem_info = info.get("memory_info")
                mem_mb = (mem_info.rss / 1024 / 1024) if mem_info else 0.0
                status = info.get("status") or ""
                create_time = info.get("create_time") or 0.0

                entry = ProcessEntry(
                    pid=info["pid"],
                    name=name,
                    exe_path=exe_path,
                    cmdline=cmdline,
                    username=username,
                    cpu_percent=cpu_pct,
                    memory_mb=mem_mb,
                    status=status,
                    create_time=create_time,
                    is_protected=name.lower() in _PROTECTED_PROCESSES,
                )

                # Analyze for suspicion
                if not entry.is_protected:
                    self._analyze(entry)

                entries.append(entry)
                result.total_cpu += cpu_pct
                result.total_ram_mb += mem_mb

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        result.all_processes = sorted(entries, key=lambda p: p.suspicion_score, reverse=True)
        result.suspicious = [p for p in result.all_processes if p.is_suspicious]

        if self._progress_cb:
            self._progress_cb("Analysis complete", total, total)

        return result

    def _analyze(self, entry: ProcessEntry) -> None:
        """Analyze a process for suspicious indicators."""
        name_lower = entry.name.lower()
        exe_lower = entry.exe_path.lower() if entry.exe_path else ""
        cmd_lower = entry.cmdline.lower()

        # 1. Suspicious name match
        for sus_name in _SUSPICIOUS_NAMES:
            if sus_name in name_lower or sus_name in cmd_lower:
                entry.reasons.append(SuspicionReason(
                    category="suspicious_name",
                    description=f"Known suspicious name: {sus_name}",
                    severity="critical",
                    score=40,
                ))
                break

        # 2. Running from high-risk paths
        for path_pattern in _HIGH_RISK_PATHS:
            if path_pattern in exe_lower:
                entry.reasons.append(SuspicionReason(
                    category="risky_path",
                    description=f"Running from risky location: {path_pattern.strip(chr(92))}",
                    severity="high",
                    score=30,
                ))
                break

        # 3. No executable path (hidden process)
        if not entry.exe_path and entry.name.lower() not in _PROTECTED_PROCESSES:
            entry.reasons.append(SuspicionReason(
                category="no_exe",
                description="No executable path (potentially hidden)",
                severity="medium",
                score=15,
            ))

        # 4. Excessive CPU usage (>70% sustained)
        if entry.cpu_percent > 70:
            entry.reasons.append(SuspicionReason(
                category="high_cpu",
                description=f"Very high CPU usage: {entry.cpu_percent:.1f}%",
                severity="high",
                score=25,
            ))
        elif entry.cpu_percent > 40:
            entry.reasons.append(SuspicionReason(
                category="high_cpu",
                description=f"High CPU usage: {entry.cpu_percent:.1f}%",
                severity="medium",
                score=15,
            ))

        # 5. Excessive memory (>1GB for non-system)
        if entry.memory_mb > 1024:
            entry.reasons.append(SuspicionReason(
                category="high_memory",
                description=f"Very high RAM usage: {entry.memory_mb:.0f} MB",
                severity="medium",
                score=15,
            ))

        # 6. Suspicious file extensions in path
        suspicious_exts = (".tmp", ".scr", ".pif", ".com", ".cmd.exe")
        for ext in suspicious_exts:
            if exe_lower.endswith(ext):
                entry.reasons.append(SuspicionReason(
                    category="suspicious_ext",
                    description=f"Suspicious file extension: {ext}",
                    severity="high",
                    score=25,
                ))
                break

        # 7. Process name mimicking system process (e.g. "svchost" without .exe)
        system_mimics = ["svchost", "csrss", "lsass", "explorer", "winlogon"]
        for sys_name in system_mimics:
            if (sys_name in name_lower
                    and name_lower != f"{sys_name}.exe"
                    and name_lower != sys_name):
                entry.reasons.append(SuspicionReason(
                    category="name_mimic",
                    description=f"Possibly mimicking system process: {sys_name}",
                    severity="critical",
                    score=35,
                ))
                break

        # 8. Running from user's Downloads folder
        if "\\downloads\\" in exe_lower:
            entry.reasons.append(SuspicionReason(
                category="downloads_path",
                description="Running directly from Downloads folder",
                severity="low",
                score=10,
            ))

        # Calculate total score (cap at 100)
        entry.suspicion_score = min(
            sum(r.score for r in entry.reasons), 100
        )

    def kill_process(self, pid: int, force: bool = False) -> tuple[bool, str]:
        """Kill a process by PID. Returns (success, message)."""
        try:
            proc = psutil.Process(pid)
            name = proc.name()

            # Safety check
            if name.lower() in _PROTECTED_PROCESSES:
                return False, f"Cannot kill protected system process: {name}"

            if force:
                proc.kill()
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    proc.kill()

            return True, f"Process {name} (PID {pid}) terminated"

        except psutil.NoSuchProcess:
            return False, f"Process {pid} no longer exists"
        except psutil.AccessDenied:
            return False, f"Access denied — run as Administrator to kill PID {pid}"
        except Exception as e:
            return False, f"Error killing PID {pid}: {e}"

    def kill_all_suspicious(
        self,
        processes: list[ProcessEntry],
        min_severity: str = "high",
    ) -> tuple[int, int, list[str]]:
        """Kill all suspicious processes above a severity threshold.
        
        Returns (killed, failed, error_messages).
        """
        severity_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        threshold = severity_order.get(min_severity, 3)

        killed = 0
        failed = 0
        errors: list[str] = []

        for proc in processes:
            proc_severity = severity_order.get(proc.severity, 0)
            if proc_severity < threshold:
                continue
            if proc.is_protected:
                continue

            ok, msg = self.kill_process(proc.pid)
            if ok:
                killed += 1
            else:
                failed += 1
                errors.append(msg)

        return killed, failed, errors

    def suspend_process(self, pid: int) -> tuple[bool, str]:
        """Suspend (pause) a process."""
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            if name.lower() in _PROTECTED_PROCESSES:
                return False, f"Cannot suspend protected process: {name}"
            proc.suspend()
            return True, f"Process {name} (PID {pid}) suspended"
        except psutil.NoSuchProcess:
            return False, f"Process {pid} no longer exists"
        except psutil.AccessDenied:
            return False, f"Access denied — run as Administrator"
        except Exception as e:
            return False, f"Error: {e}"

    def resume_process(self, pid: int) -> tuple[bool, str]:
        """Resume a suspended process."""
        try:
            proc = psutil.Process(pid)
            proc.resume()
            return True, f"Process {proc.name()} (PID {pid}) resumed"
        except psutil.NoSuchProcess:
            return False, f"Process {pid} no longer exists"
        except psutil.AccessDenied:
            return False, f"Access denied"
        except Exception as e:
            return False, f"Error: {e}"
