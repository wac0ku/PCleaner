"""Disk usage analyzer — breaks down disk usage by file type and folder."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# File type categories and their extensions
FILE_CATEGORIES: dict[str, list[str]] = {
    "Images":     [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg", ".ico", ".heic", ".raw"],
    "Videos":     [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".3gp"],
    "Audio":      [".mp3", ".flac", ".wav", ".aac", ".ogg", ".wma", ".m4a", ".opus", ".aiff"],
    "Documents":  [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".odt", ".ods"],
    "Archives":   [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".cab"],
    "Code":       [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".h", ".cs", ".php", ".go", ".rs"],
    "Executables":[".exe", ".msi", ".dll", ".sys", ".bat", ".cmd", ".ps1"],
    "Data":       [".db", ".sqlite", ".json", ".xml", ".csv", ".yaml", ".yml", ".toml", ".ini", ".cfg"],
    "Other":      [],  # catch-all
}

_EXT_MAP: dict[str, str] = {}
for _cat, _exts in FILE_CATEGORIES.items():
    for _ext in _exts:
        _EXT_MAP[_ext] = _cat


def _categorize(path: Path) -> str:
    return _EXT_MAP.get(path.suffix.lower(), "Other")


@dataclass
class FileEntry:
    path: Path
    size: int
    category: str


@dataclass
class DiskCategory:
    name: str
    size: int = 0
    count: int = 0
    files: list[FileEntry] = field(default_factory=list)

    @property
    def size_str(self) -> str:
        n = float(self.size)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"

    @property
    def avg_size_str(self) -> str:
        if self.count == 0:
            return "—"
        return DiskCategory("", self.size // self.count).size_str


@dataclass
class DirEntry:
    path: Path
    size: int
    file_count: int

    @property
    def size_str(self) -> str:
        n: float = float(self.size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} PB"


@dataclass
class AnalysisResult:
    root: Path
    categories: dict[str, DiskCategory] = field(default_factory=dict)
    largest_dirs: list[DirEntry] = field(default_factory=list)
    total_size: int = 0
    total_files: int = 0

    @property
    def total_size_str(self) -> str:
        n = float(self.total_size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} PB"

    def sorted_categories(self) -> list[DiskCategory]:
        return sorted(self.categories.values(), key=lambda c: c.size, reverse=True)

    def percent(self, category: str) -> float:
        if self.total_size == 0:
            return 0.0
        return self.categories.get(category, DiskCategory("")).size / self.total_size * 100


class DiskAnalyzer:
    """Scans a directory and produces a breakdown of disk usage."""

    def __init__(self) -> None:
        self._progress_cb: Callable[[str, int], None] | None = None

    def set_progress_callback(self, cb: Callable[[str, int], None]) -> None:
        """cb(current_path, files_counted)"""
        self._progress_cb = cb

    def analyze(self, root: Path, max_depth: int = 6) -> AnalysisResult:
        result = AnalysisResult(root=root)
        # Init categories
        for cat in FILE_CATEGORIES:
            result.categories[cat] = DiskCategory(cat)

        dir_sizes: dict[Path, int] = {}
        file_count = 0

        for dirpath_str, dirnames, filenames in os.walk(root):
            dirpath = Path(dirpath_str)
            # Skip system/hidden dirs
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in
                          {"$RECYCLE.BIN", "System Volume Information", "Windows", "Program Files"}]

            depth = len(dirpath.relative_to(root).parts)
            if depth > max_depth:
                dirnames.clear()
                continue

            dir_size = 0
            for fname in filenames:
                fpath = dirpath / fname
                try:
                    size = fpath.stat().st_size
                except OSError:
                    continue
                cat = _categorize(fpath)
                entry = FileEntry(path=fpath, size=size, category=cat)
                result.categories[cat].size += size
                result.categories[cat].count += 1
                result.categories[cat].files.append(entry)
                result.total_size += size
                result.total_files += 1
                dir_size += size
                file_count += 1
                if self._progress_cb and file_count % 500 == 0:
                    self._progress_cb(str(dirpath), file_count)

            dir_sizes[dirpath] = dir_size

        # Compute top directories
        dir_entries = [
            DirEntry(path=p, size=s, file_count=0)
            for p, s in sorted(dir_sizes.items(), key=lambda x: x[1], reverse=True)[:20]
        ]
        result.largest_dirs = dir_entries
        return result

    def get_drive_info(self) -> list[dict]:
        """Return info for all available drives."""
        import shutil
        import string
        drives = []
        for letter in string.ascii_uppercase:
            path = Path(f"{letter}:\\")
            if path.exists():
                try:
                    total, used, free = shutil.disk_usage(path)
                    drives.append({
                        "drive": f"{letter}:\\",
                        "total": total,
                        "used": used,
                        "free": free,
                        "percent_used": used / total * 100 if total > 0 else 0,
                    })
                except OSError:
                    pass
        return drives
