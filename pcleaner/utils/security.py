"""Security utilities: path sanitization, input validation, safe subprocess."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Sequence

from pcleaner.utils.logger import log


# ---------------------------------------------------------------------------
# Path sanitization
# ---------------------------------------------------------------------------

class PathTraversalError(ValueError):
    """Raised when a path attempts to escape its allowed root."""


def safe_path(user_path: str | Path, allowed_root: str | Path | None = None) -> Path:
    """Resolve and validate a user-supplied path.

    If *allowed_root* is given the resolved path must stay inside it.
    Raises PathTraversalError on attempted traversal.
    """
    try:
        resolved = Path(user_path).resolve()
    except (TypeError, ValueError) as exc:
        raise PathTraversalError(f"Invalid path: {user_path!r}") from exc

    if allowed_root is not None:
        root = Path(allowed_root).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            raise PathTraversalError(
                f"Path {resolved!r} escapes allowed root {root!r}"
            )

    return resolved


def validate_drive_letter(drive: str) -> str:
    """Ensure *drive* is a valid Windows drive letter (e.g. 'C:\\').

    Returns the normalised 'X:\\' form or raises ValueError.
    """
    m = re.match(r"^([A-Za-z])(?::\\?)?$", drive.strip())
    if not m:
        raise ValueError(f"Invalid drive letter: {drive!r}")
    return f"{m.group(1).upper()}:\\"


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

_SAFE_NAME_RE = re.compile(r"^[\w\s\-.()\[\]]{1,256}$", re.UNICODE)


def validate_name(name: str, field: str = "name") -> str:
    """Validate a human-readable name (program name, startup entry, etc.)."""
    if not name or not name.strip():
        raise ValueError(f"{field} must not be empty")
    if len(name) > 256:
        raise ValueError(f"{field} exceeds 256 characters")
    return name.strip()


def validate_wiper_passes(passes: int) -> int:
    """Passes must be one of the recognised standards."""
    allowed = {1, 3, 7, 35}
    if passes not in allowed:
        raise ValueError(f"passes must be one of {sorted(allowed)}, got {passes}")
    return passes


# ---------------------------------------------------------------------------
# Safe subprocess helpers (never use shell=True with user data)
# ---------------------------------------------------------------------------

def run_safe(
    args: Sequence[str],
    *,
    timeout: int = 30,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """Run a subprocess with shell=False and a timeout.

    All args must be strings; caller must never build args via f-strings
    from untrusted user input.
    """
    str_args = [str(a) for a in args]
    log.debug("run_safe: %s", str_args)
    return subprocess.run(
        str_args,
        shell=False,
        capture_output=capture,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


def run_powershell(script: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a PowerShell script safely (script is not user input)."""
    return run_safe(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        timeout=timeout,
    )
