"""Security utility tests — PathTraversalError, input validation, safe subprocess."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

from pcleaner.utils.security import (
    PathTraversalError,
    safe_path,
    validate_drive_letter,
    validate_name,
    validate_wiper_passes,
    run_safe,
)


# ---------------------------------------------------------------------------
# safe_path
# ---------------------------------------------------------------------------

class TestSafePath:
    def test_resolves_path(self, tmp_path):
        result = safe_path(tmp_path)
        assert result == tmp_path.resolve()

    def test_accepts_path_inside_root(self, tmp_path):
        child = tmp_path / "a" / "b.txt"
        result = safe_path(child, allowed_root=tmp_path)
        assert result == child.resolve()

    def test_blocks_traversal_dotdot(self, tmp_path):
        traversal = tmp_path / ".." / "outside"
        with pytest.raises(PathTraversalError):
            safe_path(traversal, allowed_root=tmp_path)

    def test_blocks_absolute_path_outside_root(self, tmp_path):
        other = Path(tempfile.gettempdir()) / "other"
        with pytest.raises(PathTraversalError):
            safe_path(other, allowed_root=tmp_path)

    def test_no_root_allows_any_path(self, tmp_path):
        result = safe_path(tmp_path / "sub" / "file.txt")
        assert isinstance(result, Path)

    def test_invalid_type_raises(self):
        with pytest.raises(PathTraversalError):
            safe_path(None)  # type: ignore[arg-type]

    def test_root_itself_is_allowed(self, tmp_path):
        result = safe_path(tmp_path, allowed_root=tmp_path)
        assert result == tmp_path.resolve()


# ---------------------------------------------------------------------------
# validate_drive_letter
# ---------------------------------------------------------------------------

class TestValidateDriveLetter:
    @pytest.mark.parametrize("inp,expected", [
        ("C",    "C:\\"),
        ("c",    "C:\\"),
        ("C:",   "C:\\"),
        ("C:\\", "C:\\"),
        ("D:\\", "D:\\"),
        ("z",    "Z:\\"),
    ])
    def test_valid_inputs(self, inp, expected):
        assert validate_drive_letter(inp) == expected

    @pytest.mark.parametrize("bad", ["", "CD", "1:", "\\", "C:\\Windows", "//server"])
    def test_invalid_inputs(self, bad):
        with pytest.raises(ValueError):
            validate_drive_letter(bad)


# ---------------------------------------------------------------------------
# validate_name
# ---------------------------------------------------------------------------

class TestValidateName:
    def test_valid_name(self):
        assert validate_name("My App") == "My App"

    def test_strips_whitespace(self):
        assert validate_name("  test  ") == "test"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            validate_name("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            validate_name("   ")

    def test_too_long_raises(self):
        with pytest.raises(ValueError):
            validate_name("x" * 257)

    def test_max_length_ok(self):
        assert validate_name("x" * 256) == "x" * 256


# ---------------------------------------------------------------------------
# validate_wiper_passes
# ---------------------------------------------------------------------------

class TestValidateWiperPasses:
    @pytest.mark.parametrize("n", [1, 3, 7, 35])
    def test_valid_passes(self, n):
        assert validate_wiper_passes(n) == n

    @pytest.mark.parametrize("bad", [0, 2, 4, 5, 8, 36, -1, 100])
    def test_invalid_passes(self, bad):
        with pytest.raises(ValueError):
            validate_wiper_passes(bad)


# ---------------------------------------------------------------------------
# run_safe
# ---------------------------------------------------------------------------

class TestRunSafe:
    def test_runs_simple_command(self):
        result = run_safe(["python", "--version"])
        assert result.returncode == 0
        assert "Python" in result.stdout or "Python" in result.stderr

    def test_captures_output(self):
        result = run_safe(["python", "-c", "print('hello')"])
        assert "hello" in result.stdout

    def test_timeout_raises(self):
        import subprocess
        with pytest.raises(subprocess.TimeoutExpired):
            run_safe(["python", "-c", "import time; time.sleep(10)"], timeout=1)

    def test_nonexistent_command_raises(self):
        with pytest.raises(FileNotFoundError):
            run_safe(["__nonexistent_command_xyz__"])

    def test_no_shell_injection(self):
        # Shell metacharacter in argument must NOT execute extra command
        result = run_safe(["python", "-c", "print('safe')"], capture=True)
        assert result.returncode == 0
        assert "safe" in result.stdout
