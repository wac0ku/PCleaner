"""System health check — CPU, RAM, disk, startup items, and recommendations."""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime

import psutil

from pcleaner.utils.logger import log


@dataclass
class DriveInfo:
    drive: str
    total: int
    used: int
    free: int

    @property
    def percent_used(self) -> float:
        return self.used / self.total * 100 if self.total > 0 else 0.0

    def _fmt(self, n: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n} TB"

    @property
    def total_str(self) -> str: return self._fmt(self.total)
    @property
    def used_str(self) -> str: return self._fmt(self.used)
    @property
    def free_str(self) -> str: return self._fmt(self.free)


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    memory_mb: float
    status: str


@dataclass
class HealthReport:
    # System
    os_name: str = ""
    os_version: str = ""
    hostname: str = ""
    cpu_brand: str = ""
    cpu_cores: int = 0
    cpu_threads: int = 0
    cpu_freq_mhz: float = 0.0
    cpu_usage: float = 0.0

    # RAM
    ram_total: int = 0
    ram_used: int = 0
    ram_free: int = 0
    ram_percent: float = 0.0

    # Drives
    drives: list[DriveInfo] = field(default_factory=list)

    # Processes
    top_processes: list[ProcessInfo] = field(default_factory=list)
    total_processes: int = 0

    # Startup
    startup_count: int = 0

    # Uptime
    boot_time: datetime = field(default_factory=datetime.now)

    # Recommendations
    recommendations: list[str] = field(default_factory=list)

    def _fmt(self, n: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n} GB"

    @property
    def ram_total_str(self) -> str: return self._fmt(self.ram_total)
    @property
    def ram_used_str(self) -> str: return self._fmt(self.ram_used)
    @property
    def ram_free_str(self) -> str: return self._fmt(self.ram_free)

    @property
    def uptime_str(self) -> str:
        delta = datetime.now() - self.boot_time
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        if h > 0:
            return f"{h}h {m}m"
        return f"{m}m {s}s"


class HealthChecker:
    """Gathers comprehensive system health information."""

    def check(self) -> HealthReport:
        report = HealthReport()
        self._check_system(report)
        self._check_cpu(report)
        self._check_ram(report)
        self._check_drives(report)
        self._check_processes(report)
        self._check_startup(report)
        self._generate_recommendations(report)
        return report

    def _check_system(self, r: HealthReport) -> None:
        r.os_name = platform.system()
        r.os_version = platform.version()
        r.hostname = platform.node()
        try:
            r.boot_time = datetime.fromtimestamp(psutil.boot_time())
        except Exception:
            r.boot_time = datetime.now()

        # Try to get Windows version friendly name
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-WmiObject -Class Win32_OperatingSystem).Caption"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                r.os_name = result.stdout.strip()
        except Exception:
            pass

    def _check_cpu(self, r: HealthReport) -> None:
        try:
            r.cpu_cores = psutil.cpu_count(logical=False) or 0
            r.cpu_threads = psutil.cpu_count(logical=True) or 0
            r.cpu_usage = psutil.cpu_percent(interval=0.5)
            freq = psutil.cpu_freq()
            if freq:
                r.cpu_freq_mhz = freq.current
        except Exception as e:
            log.debug("CPU check failed: %s", e)

        # CPU brand via platform
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-WmiObject -Class Win32_Processor).Name"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                r.cpu_brand = result.stdout.strip()
        except Exception:
            r.cpu_brand = platform.processor()

    def _check_ram(self, r: HealthReport) -> None:
        try:
            mem = psutil.virtual_memory()
            r.ram_total = mem.total
            r.ram_used = mem.used
            r.ram_free = mem.available
            r.ram_percent = mem.percent
        except Exception as e:
            log.debug("RAM check failed: %s", e)

    def _check_drives(self, r: HealthReport) -> None:
        try:
            for part in psutil.disk_partitions(all=False):
                if "cdrom" in part.opts or part.fstype == "":
                    continue
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    r.drives.append(DriveInfo(
                        drive=part.mountpoint,
                        total=usage.total,
                        used=usage.used,
                        free=usage.free,
                    ))
                except (PermissionError, OSError):
                    pass
        except Exception as e:
            log.debug("Drive check failed: %s", e)

    def _check_processes(self, r: HealthReport) -> None:
        try:
            procs: list[ProcessInfo] = []
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
                try:
                    info = proc.info
                    mem_mb = (info["memory_info"].rss / 1024 / 1024) if info.get("memory_info") else 0
                    procs.append(ProcessInfo(
                        pid=info["pid"],
                        name=info["name"] or "?",
                        cpu_percent=info["cpu_percent"] or 0.0,
                        memory_mb=mem_mb,
                        status=info["status"] or "",
                    ))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            r.total_processes = len(procs)
            r.top_processes = sorted(procs, key=lambda p: p.memory_mb, reverse=True)[:15]
        except Exception as e:
            log.debug("Process check failed: %s", e)

    def _check_startup(self, r: HealthReport) -> None:
        try:
            from pcleaner.tools.startup import StartupManager
            entries = StartupManager().list_entries()
            r.startup_count = len([e for e in entries if e.enabled])
        except Exception as e:
            log.debug("Startup check failed: %s", e)

    def _generate_recommendations(self, r: HealthReport) -> None:
        recs = r.recommendations

        if r.ram_percent > 85:
            recs.append(f"High RAM usage ({r.ram_percent:.0f}%). Consider closing unused applications.")

        if r.cpu_usage > 80:
            recs.append(f"High CPU usage ({r.cpu_usage:.0f}%). Check top processes in Task Manager.")

        for drive in r.drives:
            if drive.percent_used > 90:
                recs.append(f"Drive {drive.drive} is {drive.percent_used:.0f}% full. Run the Cleaner to free space.")
            elif drive.percent_used > 75:
                recs.append(f"Drive {drive.drive} is {drive.percent_used:.0f}% full. Consider cleaning junk files.")

        if r.startup_count > 15:
            recs.append(
                f"{r.startup_count} programs start with Windows. Disable unused ones in Startup Manager."
            )

        if not recs:
            recs.append("Your system looks healthy! Run the Cleaner periodically to maintain performance.")
