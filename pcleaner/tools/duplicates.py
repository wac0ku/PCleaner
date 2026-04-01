"""Duplicate file finder using size pre-filter + MD5 hashing."""

from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pcleaner.utils.logger import log

CHUNK_SIZE = 65536  # 64 KB


def _hash_file(path: Path) -> str | None:
    """Compute MD5 hash of a file. Returns None on error."""
    h = hashlib.md5()
    try:
        with path.open("rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, OSError) as e:
        log.debug("Could not hash %s: %s", path, e)
        return None


@dataclass
class DuplicateGroup:
    hash: str
    size: int
    files: list[Path] = field(default_factory=list)

    @property
    def wasted_bytes(self) -> int:
        return self.size * (len(self.files) - 1)

    @property
    def size_str(self) -> str:
        n = float(self.size)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"

    @property
    def wasted_str(self) -> str:
        n = float(self.wasted_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"


@dataclass
class DuplicateResult:
    groups: list[DuplicateGroup] = field(default_factory=list)
    scanned_files: int = 0
    scanned_bytes: int = 0

    @property
    def total_wasted(self) -> int:
        return sum(g.wasted_bytes for g in self.groups)

    @property
    def total_wasted_str(self) -> str:
        n = float(self.total_wasted)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"

    def sorted_by_wasted(self) -> list[DuplicateGroup]:
        return sorted(self.groups, key=lambda g: g.wasted_bytes, reverse=True)


class DuplicateFinder:
    """Finds duplicate files via size pre-grouping then MD5 hashing."""

    def __init__(
        self,
        min_size: int = 1024,            # Skip files smaller than 1 KB
        ignore_hidden: bool = True,
        ignore_system: bool = True,
        extensions: list[str] | None = None,  # None = all extensions
    ) -> None:
        self.min_size = min_size
        self.ignore_hidden = ignore_hidden
        self.ignore_system = ignore_system
        self.extensions = {e.lower() for e in extensions} if extensions else None
        self._progress_cb: Callable[[str, int, int], None] | None = None

    def set_progress_callback(self, cb: Callable[[str, int, int], None]) -> None:
        """cb(phase_label, current, total)"""
        self._progress_cb = cb

    def scan(self, paths: list[Path]) -> DuplicateResult:
        result = DuplicateResult()

        # Phase 1: Collect all files grouped by size
        size_groups: dict[int, list[Path]] = defaultdict(list)
        for root_path in paths:
            self._collect_files(root_path, size_groups, result)

        # Phase 2: Hash files that share a size
        candidates = {sz: files for sz, files in size_groups.items() if len(files) > 1}
        total_candidates = sum(len(f) for f in candidates.values())
        hashed = 0

        hash_groups: dict[str, list[Path]] = defaultdict(list)
        for size, files in candidates.items():
            for fpath in files:
                h = _hash_file(fpath)
                if h:
                    hash_groups[h].append(fpath)
                hashed += 1
                if self._progress_cb and hashed % 50 == 0:
                    self._progress_cb("Hashing files", hashed, total_candidates)

        # Phase 3: Build duplicate groups
        for h, files in hash_groups.items():
            if len(files) > 1:
                size = files[0].stat().st_size if files[0].exists() else 0
                result.groups.append(DuplicateGroup(hash=h, size=size, files=files))

        result.groups.sort(key=lambda g: g.wasted_bytes, reverse=True)
        return result

    def _collect_files(
        self, root: Path, size_groups: dict[int, list[Path]], result: DuplicateResult
    ) -> None:
        if self._progress_cb:
            self._progress_cb("Scanning files", result.scanned_files, -1)

        for dirpath, dirnames, filenames in os.walk(root):
            # Skip hidden dirs
            if self.ignore_hidden:
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            dirnames[:] = [d for d in dirnames if d not in
                          {"$RECYCLE.BIN", "System Volume Information"}]

            for fname in filenames:
                if self.ignore_hidden and fname.startswith("."):
                    continue
                fpath = Path(dirpath) / fname
                if self.extensions and fpath.suffix.lower() not in self.extensions:
                    continue
                try:
                    stat = fpath.stat()
                    if stat.st_size < self.min_size:
                        continue
                    size_groups[stat.st_size].append(fpath)
                    result.scanned_files += 1
                    result.scanned_bytes += stat.st_size
                except (PermissionError, OSError):
                    pass

    def delete_duplicates(
        self,
        groups: list[DuplicateGroup],
        keep: str = "newest",  # "newest", "oldest", "first"
        dry_run: bool = False,
    ) -> tuple[int, int]:
        """Delete duplicate files keeping one copy per group. Returns (deleted, errors)."""
        deleted = 0
        errors = 0
        for group in groups:
            files = list(group.files)
            if len(files) <= 1:
                continue

            # Sort to determine which to keep
            if keep == "newest":
                files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
            elif keep == "oldest":
                files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0)

            # Keep first, delete rest
            to_delete = files[1:]
            for f in to_delete:
                if dry_run:
                    deleted += 1
                    continue
                try:
                    f.unlink()
                    deleted += 1
                    log.info("Deleted duplicate: %s", f)
                except OSError as e:
                    log.warning("Failed to delete %s: %s", f, e)
                    errors += 1

        return deleted, errors
