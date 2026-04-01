"""UAC elevation utilities for Windows."""

from __future__ import annotations

import ctypes
import sys


def is_admin() -> bool:
    """Return True if the current process has administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except AttributeError:
        return False


def request_elevation(extra_args: list[str] | None = None) -> None:
    """Re-launch the current process with UAC elevation and exit the current one.

    If the user declines UAC, ShellExecuteW returns ≤32 and we silently return.
    """
    args = sys.argv[:]
    if extra_args:
        args.extend(extra_args)
    params = " ".join(f'"{a}"' if " " in a else a for a in args[1:])
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    if ret > 32:
        sys.exit(0)


def require_admin(message: str = "This operation requires administrator privileges.") -> bool:
    """Return True if admin. Print message and return False if not."""
    if is_admin():
        return True
    print(f"[yellow]Warning:[/] {message}")
    return False
