"""Shared formatting utilities."""

from __future__ import annotations


def fmt_size(n: int | float) -> str:
    """Convert a byte count to a human-readable string (e.g. '1.4 GB')."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
