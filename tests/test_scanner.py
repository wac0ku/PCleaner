"""Tests for the core scanning engine."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from pcleaner.core.scanner import CleanItem, Scanner, ScanResult, _dir_size
from pcleaner.utils.format import fmt_size as _fmt_size
from pcleaner.core.browsers import installed_browsers, get_browser_paths


# ── Unit tests ──────────────────────────────────────────────────────────────

class TestFmtSize:
    def test_bytes(self):
        assert "512.0 B" == _fmt_size(512)

    def test_kilobytes(self):
        assert "1.0 KB" == _fmt_size(1024)

    def test_megabytes(self):
        assert "1.0 MB" == _fmt_size(1024 * 1024)

    def test_gigabytes(self):
        assert "1.0 GB" == _fmt_size(1024 ** 3)


class TestDirSize:
    def test_empty_dir(self, tmp_path):
        assert _dir_size(tmp_path) == 0

    def test_single_file(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_bytes(b"x" * 100)
        assert _dir_size(tmp_path) == 100

    def test_nested_files(self, tmp_path):
        (tmp_path / "a").write_bytes(b"x" * 50)
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b").write_bytes(b"x" * 50)
        assert _dir_size(tmp_path) == 100

    def test_nonexistent(self):
        assert _dir_size(Path("/nonexistent/path")) == 0


class TestCleanItem:
    def test_size_str(self):
        item = CleanItem(
            category="Temp", subcategory="Test", path=Path("x"),
            size=1024 * 1024, description="test", safe=True,
        )
        assert item.size_str == "1.0 MB"

    def test_defaults(self):
        item = CleanItem(category="C", subcategory="S", path=Path("x"))
        assert item.enabled is True
        assert item.safe is True
        assert item.requires_admin is False


class TestScanResult:
    def _make_result(self, sizes: list[int], enabled: list[bool]) -> ScanResult:
        items = [
            CleanItem(category="C", subcategory="S", path=Path("x"),
                      size=s, description="", enabled=e)
            for s, e in zip(sizes, enabled)
        ]
        return ScanResult(items=items)

    def test_total_size_only_enabled(self):
        result = self._make_result([100, 200, 300], [True, False, True])
        assert result.total_size == 400

    def test_item_count(self):
        result = self._make_result([1, 2, 3], [True, True, True])
        assert result.item_count == 3

    def test_by_category(self):
        items = [
            CleanItem(category="A", subcategory="s", path=Path("x"), size=1),
            CleanItem(category="B", subcategory="s", path=Path("x"), size=2),
            CleanItem(category="A", subcategory="s", path=Path("x"), size=3),
        ]
        result = ScanResult(items=items)
        cats = result.by_category()
        assert "A" in cats
        assert "B" in cats
        assert len(cats["A"]) == 2
        assert len(cats["B"]) == 1


# ── Integration smoke tests ─────────────────────────────────────────────────

class TestScanner:
    def test_scan_all_returns_result(self):
        scanner = Scanner()
        result = scanner.scan_all()
        assert isinstance(result, ScanResult)
        assert isinstance(result.items, list)

    def test_scan_category_temp(self):
        scanner = Scanner()
        items = scanner.scan_category("temp_files")
        assert isinstance(items, list)
        # All items should be in the Temp Files category
        for item in items:
            assert item.category == "Temp Files"

    def test_scan_recycle_bin(self):
        scanner = Scanner()
        items = scanner.scan_category("recycle_bin")
        assert isinstance(items, list)

    def test_progress_callback(self):
        calls: list[tuple] = []
        scanner = Scanner()
        scanner.set_progress_callback(lambda label, cur, tot: calls.append((label, cur, tot)))
        scanner.scan_all(["temp_files"])
        assert len(calls) > 0

    def test_last_result_updated(self):
        scanner = Scanner()
        scanner.scan_all(["temp_files"])
        assert scanner.last_result is not None


class TestBrowserDetection:
    def test_installed_browsers_returns_list(self):
        browsers = installed_browsers()
        assert isinstance(browsers, list)

    def test_installed_browsers_are_known(self):
        from pcleaner.core.browsers import BROWSER_PROFILES
        for b in installed_browsers():
            assert b in BROWSER_PROFILES

    def test_get_browser_paths_unknown(self):
        paths = get_browser_paths("NonExistentBrowser", "cache")
        assert paths == []
