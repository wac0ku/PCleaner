# PCleaner — the free Cleaner App

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightblue)](https://www.microsoft.com/windows)

A fully-featured, open-source replacement for CCleaner Pro — available as a modern **GUI**, a professional **TUI**, and a scriptable **CLI**, all from one install.

---

## Features

| Feature | Description |
|---|---|
| **Junk Cleaner** | Temp files, Windows Update cache, Prefetch, log files, memory dumps, Recent Files, Recycle Bin |
| **Browser Cleaner** | Cache, cookies, history, form data for Chrome, Edge, Firefox, Brave, Opera, Opera GX, Vivaldi |
| **Registry Cleaner** | Scans for broken Run keys, orphaned uninstall entries, missing file-extension handlers — auto-backup before cleaning |
| **Startup Manager** | View, enable, disable, or delete startup entries from HKCU/HKLM Run keys and Task Scheduler |
| **Software Uninstaller** | Browse all installed programs, sort by name/size/date, launch uninstallers silently in batch |
| **Disk Analyzer** | Breakdown of disk usage by file type (Images, Videos, Documents, Code …) with top-directory list |
| **Duplicate Finder** | Hash-based (MD5) duplicate detection with wasted-space reporting and safe deletion |
| **Secure Wiper** | DoD 1/3/7-pass and Gutmann 35-pass overwrite for files, directories, and free space |
| **Health Dashboard** | CPU/RAM/disk usage, top processes, startup count, uptime, and improvement recommendations |
| **DNS Flush** | One-click `ipconfig /flushdns` |
| **Clipboard Clear** | Wipe clipboard contents |

---

## Interfaces

### GUI (CustomTkinter)
A modern desktop window with dark/light theme toggle, sidebar navigation, and real-time progress bars.

```
pcleaner --gui
```

### TUI (Textual)
A full-featured terminal UI with tabbed navigation, sortable data tables, and modal confirmation dialogs.

```
pcleaner --tui
```

### CLI (Typer + Rich)
Scriptable commands with beautiful Rich output, suitable for automation and scheduled tasks.

```
pcleaner --help
```

---

## Installation

### Requirements
- Windows 10 / 11
- Python 3.10 or newer

### From source

```bash
git clone https://github.com/yourname/pcleaner.git
cd pcleaner
pip install -e .
```

### From PyPI *(coming soon)*

```bash
pip install pcleaner
```

---

## CLI Reference

```bash
# Show banner + quick-start hints
pcleaner

# Scan and clean junk files
pcleaner clean                         # Interactive — asks for confirmation
pcleaner clean --dry-run               # Preview only, nothing deleted
pcleaner clean --category temp,browser # Clean specific categories
pcleaner clean --yes                   # Skip confirmation prompt

# System health report
pcleaner health

# Secure file / directory wipe
pcleaner wipe path/to/file --passes 3  # DoD 3-pass (default)
pcleaner wipe C:\ --free-space         # Wipe free space on a drive
pcleaner wipe path/to/dir --passes 7   # DoD 7-pass on a directory

# Find and remove duplicate files
pcleaner duplicates C:\Users\YourName\Documents
pcleaner duplicates D:\Photos --delete --dry-run  # Preview deletions

# Registry
pcleaner registry scan                 # List registry issues
pcleaner registry clean                # Clean with auto-backup (asks first)
pcleaner registry clean --dry-run

# Startup programs
pcleaner startup list
pcleaner startup disable "OneDrive"
pcleaner startup enable  "OneDrive"

# Disk usage
pcleaner disk analyze C:\Users\YourName
pcleaner disk analyze D:\ --top 20

# Launch interfaces
pcleaner --gui
pcleaner --tui
pcleaner --version
```

---

## Wipe Standards

| Passes | Standard | Use case |
|---|---|---|
| 1 | Simple random | Quick delete of non-sensitive files |
| 3 | DoD 5220.22-M | Standard secure deletion |
| 7 | DoD 5220.22-M ECE | High-security environments |
| 35 | Gutmann | Maximum theoretical security |

---

## Admin Elevation

Some operations require administrator privileges (Prefetch, Windows Update cache, HKLM registry keys). PCleaner will:
- Clearly mark admin-required items in scan results
- Skip them gracefully when running without elevation
- Offer to re-launch elevated via the GUI Settings view

To run elevated manually:

```bash
# Right-click the terminal → "Run as administrator", then:
pcleaner clean
```

---

## Project Structure

```
pcleaner/
├── core/
│   ├── scanner.py       — Parallel file scanner (ThreadPoolExecutor)
│   ├── cleaner.py       — Deletion engine with progress callbacks
│   ├── registry.py      — Registry scan + backup + clean
│   ├── browsers.py      — Browser profile path definitions
│   └── wiper.py         — Secure multi-pass file overwrite
├── tools/
│   ├── startup.py       — Startup entry manager
│   ├── uninstaller.py   — Installed software lister + uninstaller
│   ├── disk_analyzer.py — Disk usage by file type
│   ├── duplicates.py    — Hash-based duplicate finder
│   └── health.py        — System health report
├── gui/                 — CustomTkinter desktop app
├── tui/                 — Textual terminal app
├── cli/                 — Typer CLI commands
└── utils/
    ├── config.py        — JSON config in %APPDATA%\PCleaner\
    ├── logger.py        — Rotating file logger
    ├── elevation.py     — UAC admin check + re-launch
    └── security.py      — Path sanitization, input validation, safe subprocess
tests/
├── test_scanner.py
├── test_registry.py
├── test_tools.py
└── test_security.py
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Lint
ruff check pcleaner/

# Build standalone .exe
pyinstaller --onefile --windowed --icon assets/icon.ico -n PCleaner pcleaner/__main__.py
```

---

## Security

- All user-supplied file paths are resolved and validated against allowed roots (`safe_path`)
- Drive letters are normalized and validated before use (`validate_drive_letter`)
- Wipe pass counts are validated against the allowed set `{1, 3, 7, 35}`
- Subprocess calls always use `shell=False` with explicit argument lists — no shell injection
- Uninstall strings from the registry are parsed with `shlex.split` before execution
- Registry is backed up via `reg export` before any modifications

---

## License

MIT — see [LICENSE](LICENSE).
