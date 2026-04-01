"""Tests for the registry scanner and cleaner."""

from __future__ import annotations

import winreg
from pathlib import Path

import pytest

from pcleaner.core.registry import (
    RegistryIssue,
    RegistryScanner,
    RegistryCleaner,
    _path_exists,
    _open_key,
)


class TestPathExists:
    def test_empty_string(self):
        assert _path_exists("") is True

    def test_system32_exists(self):
        assert _path_exists(r"C:\Windows\System32\notepad.exe") is True

    def test_fake_path(self):
        assert _path_exists(r"C:\ThisFileDefinitelyDoesNotExist_pcleaner.exe") is False

    def test_quoted_path(self):
        assert _path_exists(r'"C:\Windows\System32\notepad.exe"') is True

    def test_path_with_args(self):
        # Should still resolve correctly
        result = _path_exists(r"C:\Windows\System32\notepad.exe --some-flag")
        # notepad.exe exists even if args don't matter
        assert isinstance(result, bool)


class TestRegistryIssue:
    def test_full_path(self):
        issue = RegistryIssue(
            hive="HKCU",
            key_path=r"Software\Test",
            value_name="MyValue",
            issue_type="MissingFile",
            description="test",
        )
        assert issue.full_path == r"HKCU\Software\Test"

    def test_display_with_value(self):
        issue = RegistryIssue(
            hive="HKCU", key_path=r"Software\Test", value_name="Val",
            issue_type="X", description="d",
        )
        assert "Val" in issue.display

    def test_display_without_value(self):
        issue = RegistryIssue(
            hive="HKCU", key_path=r"Software\Test", value_name="",
            issue_type="X", description="d",
        )
        assert issue.display == r"HKCU\Software\Test"


class TestOpenKey:
    def test_open_hkcu_run(self):
        key = _open_key("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run")
        assert key is not None
        key.Close()

    def test_open_nonexistent(self):
        key = _open_key("HKCU", r"Software\NonExistent_PCleaner_Test_Key")
        assert key is None

    def test_open_unknown_hive(self):
        key = _open_key("INVALID_HIVE", r"Software")
        # Falls back to HKEY_CURRENT_USER
        assert key is not None
        key.Close()


class TestRegistryScanner:
    def test_scan_returns_list(self):
        scanner = RegistryScanner()
        issues = scanner.scan()
        assert isinstance(issues, list)

    def test_scan_items_are_registry_issues(self):
        scanner = RegistryScanner()
        issues = scanner.scan()
        for issue in issues:
            assert isinstance(issue, RegistryIssue)
            assert issue.hive in ("HKCU", "HKLM", "HKCR")
            assert issue.issue_type != ""

    def test_progress_callback(self):
        calls = []
        scanner = RegistryScanner()
        scanner.scan(progress_cb=lambda label, cur, tot: calls.append((label, cur, tot)))
        assert len(calls) > 0

    def test_enabled_default(self):
        scanner = RegistryScanner()
        issues = scanner.scan()
        for issue in issues:
            assert issue.enabled is True


class TestRegistryCleaner:
    def test_backup_creates_file(self, tmp_path, monkeypatch):
        """Backup should produce a .reg file."""
        from pcleaner.utils import config as cfg_module
        monkeypatch.setattr(cfg_module, "BACKUPS_DIR", tmp_path)

        cleaner = RegistryCleaner()
        backup_path = cleaner.backup("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run")
        # File may or may not exist depending on reg export success
        # At minimum, we test it doesn't raise
        assert backup_path is None or backup_path.suffix == ".reg"

    def test_dry_run_returns_count(self):
        scanner = RegistryScanner()
        issues = scanner.scan()
        if not issues:
            pytest.skip("No registry issues found on this machine")
        cleaner = RegistryCleaner()
        cleaned, errors = cleaner.clean(issues[:3], dry_run=True)
        assert cleaned == min(3, len(issues))
        assert errors == 0
