"""Tests for the tools modules."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest


# ── Startup Manager ─────────────────────────────────────────────────────────

class TestStartupManager:
    def test_list_returns_list(self):
        from pcleaner.tools.startup import StartupManager
        entries = StartupManager().list_entries()
        assert isinstance(entries, list)

    def test_entries_have_names(self):
        from pcleaner.tools.startup import StartupManager
        for e in StartupManager().list_entries():
            assert isinstance(e.name, str)
            assert isinstance(e.enabled, bool)
            assert e.source in ("HKCU Run", "HKLM Run", "HKCU RunOnce", "HKLM RunOnce", "Task Scheduler")


# ── Uninstaller ─────────────────────────────────────────────────────────────

class TestUninstaller:
    def test_list_programs(self):
        from pcleaner.tools.uninstaller import Uninstaller
        programs = Uninstaller().list_programs()
        assert isinstance(programs, list)
        assert len(programs) > 0

    def test_programs_have_names(self):
        from pcleaner.tools.uninstaller import Uninstaller
        for p in Uninstaller().list_programs()[:10]:
            assert p.name
            assert isinstance(p.size_kb, int)

    def test_search_filters(self):
        from pcleaner.tools.uninstaller import Uninstaller
        uninstaller = Uninstaller()
        all_progs = uninstaller.list_programs()
        if not all_progs:
            pytest.skip("No programs found")
        name_fragment = all_progs[0].name[:4].lower()
        filtered = uninstaller.search(name_fragment)
        assert len(filtered) >= 1
        assert all(name_fragment in p.name.lower() or name_fragment in p.publisher.lower()
                   for p in filtered)

    def test_sort_by_size(self):
        from pcleaner.tools.uninstaller import Uninstaller
        programs = Uninstaller().list_programs(sort_by="size")
        sizes = [p.size_kb for p in programs]
        assert sizes == sorted(sizes, reverse=True)


# ── Disk Analyzer ───────────────────────────────────────────────────────────

class TestDiskAnalyzer:
    def test_analyze_temp(self, tmp_path):
        from pcleaner.tools.disk_analyzer import DiskAnalyzer
        # Create some test files
        (tmp_path / "photo.jpg").write_bytes(b"x" * 1000)
        (tmp_path / "video.mp4").write_bytes(b"x" * 2000)
        (tmp_path / "doc.pdf").write_bytes(b"x" * 500)
        (tmp_path / "unknown.xyz").write_bytes(b"x" * 100)

        result = DiskAnalyzer().analyze(tmp_path)
        assert result.total_size == 3600
        assert result.total_files == 4
        assert result.categories["Images"].size == 1000
        assert result.categories["Videos"].size == 2000
        assert result.categories["Documents"].size == 500
        assert result.categories["Other"].size == 100

    def test_percent_calculation(self, tmp_path):
        from pcleaner.tools.disk_analyzer import DiskAnalyzer
        (tmp_path / "a.jpg").write_bytes(b"x" * 1000)
        (tmp_path / "b.jpg").write_bytes(b"x" * 1000)
        result = DiskAnalyzer().analyze(tmp_path)
        assert result.percent("Images") == pytest.approx(100.0)

    def test_sorted_categories(self, tmp_path):
        from pcleaner.tools.disk_analyzer import DiskAnalyzer
        (tmp_path / "big.mp4").write_bytes(b"x" * 5000)
        (tmp_path / "small.jpg").write_bytes(b"x" * 100)
        result = DiskAnalyzer().analyze(tmp_path)
        cats = result.sorted_categories()
        sizes = [c.size for c in cats if c.size > 0]
        assert sizes == sorted(sizes, reverse=True)

    def test_get_drive_info(self):
        from pcleaner.tools.disk_analyzer import DiskAnalyzer
        drives = DiskAnalyzer().get_drive_info()
        assert isinstance(drives, list)
        assert len(drives) > 0
        assert all("drive" in d and "total" in d and "free" in d for d in drives)


# ── Duplicate Finder ─────────────────────────────────────────────────────────

class TestDuplicateFinder:
    def _write(self, path: Path, content: bytes) -> Path:
        path.write_bytes(content)
        return path

    def test_finds_duplicates(self, tmp_path):
        from pcleaner.tools.duplicates import DuplicateFinder
        content = b"identical content " * 100
        self._write(tmp_path / "a.txt", content)
        self._write(tmp_path / "b.txt", content)
        self._write(tmp_path / "c.txt", b"different content " * 100)

        result = DuplicateFinder(min_size=100).scan([tmp_path])
        assert len(result.groups) == 1
        assert len(result.groups[0].files) == 2

    def test_no_duplicates(self, tmp_path):
        from pcleaner.tools.duplicates import DuplicateFinder
        self._write(tmp_path / "a.txt", b"content a " * 100)
        self._write(tmp_path / "b.txt", b"content b " * 100)

        result = DuplicateFinder(min_size=100).scan([tmp_path])
        assert len(result.groups) == 0

    def test_wasted_bytes(self, tmp_path):
        from pcleaner.tools.duplicates import DuplicateFinder
        content = b"x" * 2048
        self._write(tmp_path / "a.bin", content)
        self._write(tmp_path / "b.bin", content)
        self._write(tmp_path / "c.bin", content)

        result = DuplicateFinder(min_size=100).scan([tmp_path])
        assert len(result.groups) == 1
        assert result.groups[0].wasted_bytes == 2048 * 2

    def test_delete_dry_run(self, tmp_path):
        from pcleaner.tools.duplicates import DuplicateFinder
        content = b"y" * 2048
        self._write(tmp_path / "a.bin", content)
        self._write(tmp_path / "b.bin", content)

        finder = DuplicateFinder(min_size=100)
        result = finder.scan([tmp_path])
        deleted, errors = finder.delete_duplicates(result.groups, dry_run=True)
        assert deleted == 1
        assert errors == 0
        # Files should still exist (dry run)
        assert (tmp_path / "a.bin").exists()
        assert (tmp_path / "b.bin").exists()

    def test_delete_actually_deletes(self, tmp_path):
        from pcleaner.tools.duplicates import DuplicateFinder
        content = b"z" * 2048
        self._write(tmp_path / "a.bin", content)
        self._write(tmp_path / "b.bin", content)

        finder = DuplicateFinder(min_size=100)
        result = finder.scan([tmp_path])
        deleted, errors = finder.delete_duplicates(result.groups, keep="newest")
        assert deleted == 1
        assert errors == 0
        remaining = list(tmp_path.glob("*.bin"))
        assert len(remaining) == 1


# ── Health Checker ───────────────────────────────────────────────────────────

class TestHealthChecker:
    def test_check_returns_report(self):
        from pcleaner.tools.health import HealthChecker, HealthReport
        report = HealthChecker().check()
        assert isinstance(report, HealthReport)

    def test_has_system_info(self):
        from pcleaner.tools.health import HealthChecker
        report = HealthChecker().check()
        assert report.os_name
        assert report.ram_total > 0
        assert report.cpu_threads > 0

    def test_has_drives(self):
        from pcleaner.tools.health import HealthChecker
        report = HealthChecker().check()
        assert len(report.drives) > 0

    def test_recommendations_are_strings(self):
        from pcleaner.tools.health import HealthChecker
        report = HealthChecker().check()
        for rec in report.recommendations:
            assert isinstance(rec, str)

    def test_uptime_str(self):
        from pcleaner.tools.health import HealthChecker
        report = HealthChecker().check()
        assert isinstance(report.uptime_str, str)
        assert len(report.uptime_str) > 0
