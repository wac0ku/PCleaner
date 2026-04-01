"""Software uninstaller — lists installed programs and runs their uninstallers."""

from __future__ import annotations

import subprocess
import winreg
from dataclasses import dataclass
from typing import Iterator

from pcleaner.utils.logger import log

_UNINSTALL_PATHS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
]


@dataclass
class Program:
    name: str
    version: str
    publisher: str
    install_date: str
    install_location: str
    uninstall_string: str
    quiet_uninstall: str
    size_kb: int
    key_name: str
    hive: int
    key_path: str

    @property
    def size_str(self) -> str:
        kb = self.size_kb
        if kb == 0:
            return "—"
        if kb < 1024:
            return f"{kb} KB"
        mb = kb / 1024
        if mb < 1024:
            return f"{mb:.1f} MB"
        return f"{mb / 1024:.1f} GB"


def _read_program(hive: int, base_path: str, key_name: str) -> Program | None:
    """Read a single uninstall entry."""
    try:
        with winreg.OpenKey(hive, f"{base_path}\\{key_name}", 0, winreg.KEY_READ) as key:
            def _val(name: str, default: str = "") -> str:
                try:
                    v, _ = winreg.QueryValueEx(key, name)
                    return str(v).strip()
                except OSError:
                    return default

            name = _val("DisplayName")
            if not name:
                return None
            # Skip system components and updates
            system = _val("SystemComponent", "0")
            if system == "1":
                return None
            release_type = _val("ReleaseType")
            if release_type in ("Security Update", "Update Rollup", "Hotfix"):
                return None

            return Program(
                name=name,
                version=_val("DisplayVersion"),
                publisher=_val("Publisher"),
                install_date=_val("InstallDate"),
                install_location=_val("InstallLocation"),
                uninstall_string=_val("UninstallString"),
                quiet_uninstall=_val("QuietUninstallString"),
                size_kb=int(_val("EstimatedSize") or "0"),
                key_name=key_name,
                hive=hive,
                key_path=f"{base_path}\\{key_name}",
            )
    except OSError:
        return None


def _iter_programs() -> Iterator[Program]:
    seen: set[str] = set()
    for hive, base in _UNINSTALL_PATHS:
        try:
            with winreg.OpenKey(hive, base, 0, winreg.KEY_READ) as root:
                idx = 0
                while True:
                    try:
                        key_name = winreg.EnumKey(root, idx)
                        idx += 1
                        prog = _read_program(hive, base, key_name)
                        if prog and prog.name not in seen:
                            seen.add(prog.name)
                            yield prog
                    except OSError:
                        break
        except OSError:
            continue


class Uninstaller:
    """Lists and uninstalls software from the Windows registry."""

    def list_programs(self, sort_by: str = "name") -> list[Program]:
        programs = list(_iter_programs())
        if sort_by == "name":
            programs.sort(key=lambda p: p.name.lower())
        elif sort_by == "size":
            programs.sort(key=lambda p: p.size_kb, reverse=True)
        elif sort_by == "date":
            programs.sort(key=lambda p: p.install_date, reverse=True)
        elif sort_by == "publisher":
            programs.sort(key=lambda p: p.publisher.lower())
        return programs

    def uninstall(self, program: Program, quiet: bool = False) -> bool:
        """Launch the program's uninstaller.

        Security: uninstall strings come from HKLM/HKCU registry written by
        installers — they are not user-supplied free-text.  We still avoid
        shell=True and use shlex.split so the command is parsed safely.
        """
        import shlex
        cmd = program.quiet_uninstall if (quiet and program.quiet_uninstall) else program.uninstall_string
        if not cmd:
            log.warning("No uninstall string for %s", program.name)
            return False
        cmd = cmd.strip()
        try:
            log.info("Uninstalling %s: %s", program.name, cmd)
            # Parse into argv list — avoids shell interpretation entirely
            args = shlex.split(cmd, posix=False)
            subprocess.Popen(args, shell=False)
            return True
        except ValueError:
            # Malformed uninstall string — fall back to CreateProcess via os.startfile
            try:
                import os
                os.startfile(cmd)
                return True
            except Exception as e2:
                log.warning("Uninstall fallback failed for %s: %s", program.name, e2)
                return False
        except Exception as e:
            log.warning("Uninstall failed for %s: %s", program.name, e)
            return False

    def batch_uninstall(self, programs: list[Program]) -> int:
        """Uninstall multiple programs. Returns count of launched uninstallers."""
        count = 0
        for prog in programs:
            if self.uninstall(prog, quiet=True):
                count += 1
        return count

    def search(self, query: str) -> list[Program]:
        q = query.lower()
        return [p for p in self.list_programs() if q in p.name.lower() or q in p.publisher.lower()]
