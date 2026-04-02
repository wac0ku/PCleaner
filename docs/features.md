# PCleaner — Feature Reference

> Complete reference for all PCleaner features across TUI, GUI, and CLI.

---

## Table of Contents

1. [System Cleaner](#system-cleaner)
2. [Registry Cleaner](#registry-cleaner)
3. [Startup Manager](#startup-manager)
4. [Uninstaller](#uninstaller)
5. [Disk Analyzer](#disk-analyzer)
6. [Duplicate Finder](#duplicate-finder)
7. [Secure Wiper](#secure-wiper)
8. [System Health](#system-health)
9. [Task Manager](#task-manager)
10. [Quick Actions](#quick-actions)
11. [Admin Elevation](#admin-elevation)
12. [CLI Reference](#cli-reference)

---

## System Cleaner

**Module:** `pcleaner/core/scanner.py`, `pcleaner/core/cleaner.py`

Scans the system for removable junk files and deletes them safely.

### Scan Categories

| Category | Paths | Admin Required |
|---|---|---|
| Temp Files | `%TEMP%`, `%WINDIR%\Temp`, `%LOCALAPPDATA%\Temp` | No |
| Browser Cache | See Browser Paths below | No |
| Windows Update Cache | `%WINDIR%\SoftwareDistribution\Download` | Yes |
| Memory Dumps | `%WINDIR%\Minidump`, `C:\Windows\MEMORY.DMP` | No |
| Log Files | `%WINDIR%\Logs`, `%LOCALAPPDATA%\Microsoft\Windows\WER` | No |
| Recent Files | `%APPDATA%\Microsoft\Windows\Recent` | No |
| Prefetch | `%WINDIR%\Prefetch` | Yes |
| Thumbnail Cache | `%LOCALAPPDATA%\Microsoft\Windows\Explorer\thumbcache_*.db` | No |
| Recycle Bin | System recycle bin | No |

### Browser Paths

Supports: Chrome, Edge, Firefox, Brave, Opera, Vivaldi

For each browser, the following data types can be cleaned:
- **Cache** — downloaded page resources
- **Cookies** — session cookies (marks sites as unvisited)
- **History** — browsing history SQLite database
- **Form Data** — saved form auto-fill entries

> Note: Close the browser before cleaning. PCleaner warns if the browser process is running.

### CLI Usage

```bash
# Scan and clean all categories (with confirmation)
pcleaner clean

# Dry run — shows what would be cleaned without deleting
pcleaner clean --dry-run

# Clean specific categories only
pcleaner clean --category temp,browser,logs

# Skip confirmation prompt
pcleaner clean --yes
```

---

## Registry Cleaner

**Module:** `pcleaner/core/registry.py`

Scans the Windows registry for orphaned or broken entries.

### What It Scans

| Check | Registry Location |
|---|---|
| Missing executable in Run key | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |
| Broken uninstall entries | `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\*` |
| Missing shell extension DLLs | `HKCU\SOFTWARE\Classes\CLSID\*\InprocServer32` |
| Missing file handler associations | `HKCU\SOFTWARE\Classes\.ext` |

### Backup

A `.reg` export is automatically created before any cleaning operation. Backups are saved to:
```
%APPDATA%\PCleaner\backups\registry_backup_YYYYMMDD_HHMMSS.reg
```

To manually restore: right-click the `.reg` file → Merge.

### CLI Usage

```bash
pcleaner registry scan    # list issues
pcleaner registry clean   # clean (auto-backup first)
pcleaner registry backup  # backup only, no cleaning
```

---

## Startup Manager

**Module:** `pcleaner/tools/startup.py`

Lists and controls programs that run when Windows starts.

### Sources

- `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- `HKLM\Software\Microsoft\Windows\CurrentVersion\Run` (read-only without admin)
- Windows Task Scheduler startup tasks

### Actions

| Action | Effect |
|---|---|
| **Enable** | Moves entry back to `Run` key from `DisabledRun` |
| **Disable** | Moves entry to `DisabledRun` key (preserves, not deleted) |
| **Delete** | Permanently removes the entry |

### CLI Usage

```bash
pcleaner startup list           # list all startup programs
pcleaner startup disable <name> # disable by name
pcleaner startup enable <name>  # re-enable
pcleaner startup delete <name>  # permanently delete
```

---

## Uninstaller

**Module:** `pcleaner/tools/uninstaller.py`

Lists installed Windows programs and runs their official uninstallers.

### Data Source

Programs are read from:
- `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\*`
- `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\*`

### CLI Usage

```bash
pcleaner uninstall list             # list installed programs
pcleaner uninstall remove <name>    # uninstall by name
```

---

## Disk Analyzer

**Module:** `pcleaner/tools/disk_analyzer.py`

Recursively analyzes disk usage and categorizes files.

### File Categories

| Category | Extensions |
|---|---|
| Images | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.svg`, `.ico` |
| Videos | `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm` |
| Documents | `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`, `.txt`, `.odt` |
| Archives | `.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.bz2`, `.xz` |
| Code | `.py`, `.js`, `.ts`, `.html`, `.css`, `.json`, `.xml`, `.yaml`, `.toml`, `.rs`, `.go`, `.java`, `.cs`, `.cpp` |
| Other | Everything else |

### CLI Usage

```bash
pcleaner disk analyze C:/Users         # analyze a folder
pcleaner disk analyze C:/ --top 30     # show top 30 largest directories
```

---

## Duplicate Finder

**Module:** `pcleaner/tools/duplicates.py`

Finds exact duplicate files using MD5 hashing with a two-pass optimization.

### Algorithm

1. Group files by size (fast, no hashing needed for unique sizes).
2. For files sharing a size, compute MD5 hash in 8KB chunks.
3. Group by hash — any group with 2+ files are duplicates.

### CLI Usage

```bash
pcleaner duplicates C:/Users/Leon/Documents
pcleaner duplicates C:/Downloads C:/Backup   # scan multiple folders
```

---

## Secure Wiper

**Module:** `pcleaner/core/wiper.py`

Securely overwrites files before deletion to prevent forensic recovery.

### Overwrite Standards

| Standard | Passes | Notes |
|---|---|---|
| Simple (1-pass random) | 1 | Good for SSDs (wear-leveling makes more passes redundant) |
| DoD 5220.22-M (3-pass) | 3 | US DoD standard: random → zeros → ones |
| DoD 5220.22-M ECE (7-pass) | 7 | Enhanced version |
| Gutmann (35-pass) | 35 | Maximum, designed for magnetic HDDs |

### Write Performance

- Uses **4 MB write chunks** for modern SSD throughput
- Gutmann patterns pre-computed as 64 KB buffers, tiled to 4 MB for I/O
- `fsync()` called after each pass to ensure data reaches storage

### Free Space Wiping

Fills all available free space with random data, then deletes the fill file. This prevents recovery of previously deleted files that were not securely wiped.

### CLI Usage

```bash
pcleaner wipe path/to/file.txt          # wipe single file (3-pass default)
pcleaner wipe path/to/folder/           # wipe all files in folder
pcleaner wipe path/to/file --passes 7   # choose pass count: 1, 3, 7, or 35
pcleaner wipe C: --free-space           # wipe free space on C: drive
```

---

## System Health

**Module:** `pcleaner/tools/health.py`

Gathers and analyzes system metrics for a health report.

### Metrics Collected

| Metric | Source |
|---|---|
| CPU usage % | `psutil.cpu_percent()` |
| RAM usage / total | `psutil.virtual_memory()` |
| Swap / page file | `psutil.swap_memory()` |
| Disk usage per drive | `psutil.disk_partitions()` + `disk_usage()` |
| Running processes | `psutil.pids()` |
| Uptime | `psutil.boot_time()` |
| OS name + version | `platform.platform()` |
| CPU brand + cores | `psutil.cpu_freq()`, `cpu_count()` |
| Startup program count | Registry + Task Scheduler |

### Recommendations

Automatic flags:
- CPU > 80% average → "High CPU usage"
- RAM > 85% → "High memory usage — consider closing apps"
- Disk < 10 GB free → "Low disk space on `X:`"
- Startup count > 20 → "Many startup programs — consider disabling some"

### CLI Usage

```bash
pcleaner health           # full health report in terminal
pcleaner health --json    # machine-readable JSON output
```

---

## Task Manager

**Module:** `pcleaner/tui/screens/task_manager.py`

Live process viewer with process termination capability.

### Columns

| Column | Description |
|---|---|
| PID | Process ID |
| Name | Process executable name |
| CPU % | Current CPU usage |
| Memory | Working set memory |

### Actions

- **Refresh** — reload process list
- **Kill Process** — sends `SIGTERM` to selected process (confirmation required)
- **Filter** — type in search box to filter by process name

> Warning: Killing system processes may cause instability. Only kill processes you recognize.

---

## Quick Actions

Available in TUI sidebar and GUI toolbar:

| Action | Command | Description |
|---|---|---|
| Flush DNS | `ipconfig /flushdns` | Clears DNS resolver cache — fixes "site not found" issues |
| Clear Clipboard | `Set-Clipboard -Value $null` | Empties Windows clipboard |

---

## Admin Elevation

**Module:** `pcleaner/utils/elevation.py`

PCleaner can re-launch itself with administrator privileges via Windows UAC.

### How It Works

```python
ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
```

This triggers the standard Windows UAC dialog. If the user approves, the current process exits and a new elevated process starts with identical arguments.

If the user cancels UAC, nothing happens — the app continues running at normal privilege.

### When Elevation Is Needed

| Feature | Without Admin | With Admin |
|---|---|---|
| Temp Files | ✓ User temp only | ✓ System temp too |
| Windows Prefetch | ✗ Access denied | ✓ |
| SoftwareDistribution | ✗ Access denied | ✓ |
| Registry HKLM | Read-only | ✓ Full access |
| Task Scheduler | Read-only | ✓ Can modify |
| System processes | Cannot kill | ✓ |

### Detection

```python
from pcleaner.utils.elevation import is_admin
print(is_admin())  # True / False
```

---

## CLI Reference

Full command list for `pcleaner` CLI (powered by Typer + Rich):

```
pcleaner                          Show banner + interactive menu
pcleaner --tui                    Launch TUI
pcleaner --gui                    Launch GUI

pcleaner clean                    Run full clean
pcleaner clean --dry-run          Preview without deleting
pcleaner clean --category <cats>  Clean specific categories
pcleaner clean --yes              Skip confirmation

pcleaner registry scan            Scan registry for issues
pcleaner registry clean           Clean registry (auto-backup)
pcleaner registry backup          Export .reg backup only

pcleaner startup list             List startup programs
pcleaner startup disable <name>   Disable startup entry
pcleaner startup enable <name>    Enable startup entry
pcleaner startup delete <name>    Delete startup entry

pcleaner disk analyze <path>      Disk usage breakdown
pcleaner disk analyze <path> --top N  Show top N largest dirs

pcleaner duplicates <path>        Find duplicates in folder
pcleaner duplicates <p1> <p2>     Find duplicates across folders

pcleaner wipe <path>              Wipe file/folder (3-pass)
pcleaner wipe <path> --passes N   Choose: 1, 3, 7, or 35
pcleaner wipe <drive> --free-space  Wipe free space on drive

pcleaner health                   System health report
pcleaner health --json            JSON output
```

---

## File Locations

| Item | Path |
|---|---|
| Config | `%APPDATA%\PCleaner\config.json` |
| Log | `%APPDATA%\PCleaner\pcleaner.log` |
| Registry backups | `%APPDATA%\PCleaner\backups\` |
| NotebookLM session | `%USERPROFILE%\.notebooklm\profiles\default\storage_state.json` |
