"""Secure file and free-space wiper with multiple overwrite standards."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Callable

from pcleaner.utils.logger import log
from pcleaner.utils.security import safe_path, validate_drive_letter, validate_wiper_passes

CHUNK = 65536        # 64 KB — used for pre-computed Gutmann pattern buffers
WRITE_CHUNK = 4 * 1024 * 1024  # 4 MB — optimal write size for modern SSDs

WIPE_STANDARDS: dict[int, str] = {
    1:  "Simple (1-pass random)",
    3:  "DoD 5220.22-M (3-pass)",
    7:  "DoD 5220.22-M ECE (7-pass)",
    35: "Gutmann (35-pass)",
}

# Gutmann 35-pass patterns
_GUTMANN_PATTERNS: list[bytes | None] = [
    None, None, None, None,           # 1-4: random
    b"\x55" * CHUNK,                  # 5
    b"\xaa" * CHUNK,                  # 6
    b"\x92\x49\x24" * (CHUNK // 3 + 1), # 7
    b"\x49\x24\x92" * (CHUNK // 3 + 1), # 8
    b"\x24\x92\x49" * (CHUNK // 3 + 1), # 9
    b"\x00" * CHUNK,                  # 10
    b"\x11" * CHUNK,                  # 11
    b"\x22" * CHUNK,                  # 12
    b"\x33" * CHUNK,                  # 13
    b"\x44" * CHUNK,                  # 14
    b"\x55" * CHUNK,                  # 15
    b"\x66" * CHUNK,                  # 16
    b"\x77" * CHUNK,                  # 17
    b"\x88" * CHUNK,                  # 18
    b"\x99" * CHUNK,                  # 19
    b"\xaa" * CHUNK,                  # 20
    b"\xbb" * CHUNK,                  # 21
    b"\xcc" * CHUNK,                  # 22
    b"\xdd" * CHUNK,                  # 23
    b"\xee" * CHUNK,                  # 24
    b"\xff" * CHUNK,                  # 25
    b"\x92\x49\x24" * (CHUNK // 3 + 1), # 26
    b"\x49\x24\x92" * (CHUNK // 3 + 1), # 27
    b"\x24\x92\x49" * (CHUNK // 3 + 1), # 28
    b"\x6d\xb6\xdb" * (CHUNK // 3 + 1), # 29
    b"\xb6\xdb\x6d" * (CHUNK // 3 + 1), # 30
    b"\xdb\x6d\xb6" * (CHUNK // 3 + 1), # 31
    None, None, None, None,           # 32-35: random
]


def _overwrite_file(path: Path, passes: int, progress_cb: Callable | None = None) -> None:
    size = path.stat().st_size
    if size == 0:
        return

    patterns = _get_patterns(passes)
    with path.open("r+b") as f:
        for pass_num, pattern in enumerate(patterns):
            f.seek(0)
            written = 0
            while written < size:
                remaining = size - written
                if pattern is None:
                    chunk = secrets.token_bytes(min(WRITE_CHUNK, remaining))
                else:
                    # Tile the 64 KB pattern to fill a 4 MB write buffer
                    repeats = (min(WRITE_CHUNK, remaining) + len(pattern) - 1) // len(pattern)
                    chunk = (pattern * repeats)[:min(WRITE_CHUNK, remaining)]
                f.write(chunk)
                written += len(chunk)
            f.flush()
            os.fsync(f.fileno())
            if progress_cb:
                progress_cb(pass_num + 1, len(patterns))


def _get_patterns(passes: int) -> list[bytes | None]:
    if passes == 1:
        return [None]
    elif passes == 3:
        return [None, b"\x00" * CHUNK, b"\xff" * CHUNK]
    elif passes == 7:
        return [b"\x00" * CHUNK, b"\xff" * CHUNK, None,
                b"\x96" * CHUNK, None, b"\x00" * CHUNK, None]
    elif passes == 35:
        return list(_GUTMANN_PATTERNS)
    else:
        return [None] * passes


class DriveWiper:
    """Securely overwrites and deletes files or wipes free space on a drive."""

    def __init__(self, passes: int = 3, dry_run: bool = False) -> None:
        self.passes = passes
        self.dry_run = dry_run
        self._progress_cb: Callable[[str, int, int], None] | None = None

    def set_progress_callback(self, cb: Callable[[str, int, int], None]) -> None:
        """cb(label, current_pass, total_passes)"""
        self._progress_cb = cb

    def wipe_file(self, path: Path) -> bool:
        """Overwrite file with random data then delete it."""
        path = safe_path(path)
        validate_wiper_passes(self.passes)
        if not path.exists():
            return False
        if self.dry_run:
            log.info("[DryRun] Would wipe %s (%d passes)", path, self.passes)
            return True
        try:
            def _cb(p, t):
                if self._progress_cb:
                    self._progress_cb(f"Wiping {path.name}", p, t)
            _overwrite_file(path, self.passes, _cb)
            path.unlink()
            log.info("Wiped file: %s", path)
            return True
        except (PermissionError, OSError) as e:
            log.warning("Wipe failed for %s: %s", path, e)
            return False

    def wipe_directory(self, directory: Path) -> tuple[int, int]:
        """Wipe all files in a directory. Returns (wiped, failed)."""
        wiped = 0
        failed = 0
        for root, dirs, files in os.walk(directory, topdown=False):
            for fname in files:
                f = Path(root) / fname
                if self.wipe_file(f):
                    wiped += 1
                else:
                    failed += 1
            for d in dirs:
                try:
                    (Path(root) / d).rmdir()
                except OSError:
                    pass
        return wiped, failed

    def wipe_free_space(self, drive: str, progress_cb: Callable | None = None) -> bool:
        """Fill free space on a drive with random data, then delete the fill file.

        This prevents recovery of previously deleted files.
        """
        drive = validate_drive_letter(drive)
        fill_file = Path(drive) / "__pcleaner_wipe__.tmp"
        if self.dry_run:
            log.info("[DryRun] Would wipe free space on %s", drive)
            return True
        try:
            import shutil
            _, _, free = shutil.disk_usage(drive)
            written = 0
            block = WRITE_CHUNK  # 4 MB blocks
            with fill_file.open("wb") as f:
                while written < free - 10 * 1024 * 1024:  # Keep 10MB buffer
                    chunk_size = min(block, free - written - 10 * 1024 * 1024)
                    if chunk_size <= 0:
                        break
                    f.write(secrets.token_bytes(chunk_size))
                    written += chunk_size
                    if progress_cb:
                        progress_cb(written, free)
            fill_file.unlink()
            log.info("Free space wipe complete on %s (%d bytes written)", drive, written)
            return True
        except (OSError, Exception) as e:
            log.warning("Free space wipe failed on %s: %s", drive, e)
            try:
                fill_file.unlink(missing_ok=True)
            except OSError:
                pass
            return False
