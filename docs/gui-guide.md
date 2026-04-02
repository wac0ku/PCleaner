# PCleaner GUI — User Guide

> Desktop GUI powered by [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)  
> Launch: `python -m pcleaner --gui` or `pcleaner --gui`

---

## Layout

```
┌──────────────────────────────────────────────────────────────┐
│  PCleaner — the free Cleaner App          [Light/Dark] [X]  │
├───────────────┬──────────────────────────────────────────────┤
│               │                                              │
│  Health       │                                              │
│  Cleaner      │           Content Area                       │
│  Registry     │    (changes based on sidebar selection)      │
│  Startup      │                                              │
│  Uninstaller  │                                              │
│  Disk         │                                              │
│  Duplicates   │                                              │
│  Wiper        │                                              │
│  Settings     │                                              │
│               │                                              │
└───────────────┴──────────────────────────────────────────────┘
```

---

## Navigation

Click any item in the left sidebar to switch views. The active view is highlighted.

| Sidebar Item | Description |
|---|---|
| Health | System health overview |
| Cleaner | Scan and remove junk files |
| Registry | Scan and clean registry |
| Startup | Manage startup programs |
| Uninstaller | Batch uninstall programs |
| Disk | Disk usage analyzer |
| Duplicates | Duplicate file finder |
| Wiper | Secure file/drive wiper |
| Settings | App settings |

---

## Views

### Health
Displays a live system health report:

- **CPU Usage** — current usage %
- **RAM** — used / total
- **Disk** — per-drive usage summary
- **Processes** — count of running processes
- **Startup programs** — count
- **Recommendations** — flagged issues (high memory, low disk, many startup programs)

Click **Refresh** to update all metrics.

### Cleaner
Scan and delete junk files in multiple categories:

**Categories scanned:**
- Temp Files (`%TEMP%`, `%WINDIR%\Temp`, `%LOCALAPPDATA%\Temp`)
- Browser Cache (Chrome, Edge, Firefox, Brave, Opera, Vivaldi)
- Windows Update cache (`SoftwareDistribution\Download`)
- Memory Dumps (`Minidump`, `MEMORY.DMP`)
- Log Files (`%WINDIR%\Logs`, WER reports)
- Recent Files list
- Recycle Bin
- System Prefetch (requires admin)

**Workflow:**
1. Check/uncheck categories in the list.
2. Click **Analyze** — calculates sizes without deleting.
3. Review results. Total reclaimable size is shown.
4. Click **Clean Selected** — confirmation dialog appears.
5. Progress bar fills as files are deleted.

### Registry
Scan and repair broken Windows registry entries:

**What it checks:**
- `HKCU\Software\...\Run` entries pointing to missing executables
- Uninstall entries with missing DisplayIcon paths
- Shell extension handlers pointing to missing DLLs
- Class ID entries with missing InprocServer32

**Workflow:**
1. Click **Scan** — lists all detected issues.
2. Review the issue table (type, registry key, description).
3. Click **Backup** to export a `.reg` file first (recommended).
4. Click **Clean** — removes selected issues after auto-backup.

### Startup
View and manage Windows startup programs:

- Sources: `HKCU\...\Run`, `HKLM\...\Run`, Task Scheduler
- Toggle **Enable/Disable** without deleting (safe)
- **Delete** permanently removes the entry
- Shows Publisher, Path, and Status

### Uninstaller
Batch uninstall installed Windows programs:

1. Click **Refresh** to populate the list from the Windows registry.
2. Use the search box to filter by name.
3. Select one or more programs.
4. Click **Uninstall Selected** — runs each program's official uninstaller.

### Disk Analyzer
Understand where your disk space is being used:

1. Enter a folder path or click **Browse**.
2. Click **Analyze** — scans recursively.
3. Results are grouped by file type:
   - Images, Videos, Documents, Archives, Code, Other
4. Bar chart shows proportional sizes.
5. **Largest Folders** list shows top directories by size — click to open in Explorer.

### Duplicates
Find and remove duplicate files:

1. Add folder paths using **Add Folder** or **Browse**.
2. Click **Scan** — groups files by content (MD5 hash).
3. Each group shows all copies with their paths and sizes.
4. Select the copies you want to delete (keep at least one!).
5. Click **Delete Selected**.

### Wiper
Securely overwrite and delete files or wipe free space:

**File Wiper:**
1. Drag-drop or browse to select files/folders.
2. Choose overwrite standard:
   - **Simple (1-pass)** — fast, good for SSDs
   - **DoD 5220.22-M (3-pass)** — standard secure erase
   - **DoD 5220.22-M ECE (7-pass)** — enhanced
   - **Gutmann (35-pass)** — maximum, for magnetic HDDs
3. Click **Wipe Files** — confirmation required.

**Free Space Wiper:**
1. Select a drive letter (e.g., `C:`).
2. Click **Wipe Free Space** — fills free space with random data then deletes the fill file. Prevents recovery of previously deleted files.

> Warning: Wiped files cannot be recovered. Double-check before proceeding.

### Settings
Configure PCleaner preferences:

| Setting | Options |
|---|---|
| Theme | Dark / Light |
| Log level | Debug / Info / Warning |
| Scan on startup | Yes / No |
| Default wipe passes | 1 / 3 / 7 / 35 |

Changes are saved automatically to `%APPDATA%\PCleaner\config.json`.

---

## Theme Toggle

Click the **Dark/Light** toggle button in the top-right corner to switch between dark and light themes. The preference is saved and restored on next launch.

---

## Admin Elevation

Some features require administrator privileges. When you attempt an admin-only action without elevation:

1. A dialog asks if you want to re-launch as admin.
2. Windows UAC prompt appears.
3. On approval, PCleaner restarts with full privileges.

**Features requiring admin:**
- Cleaning `C:\Windows\Prefetch`
- Cleaning `C:\Windows\SoftwareDistribution\Download`
- Editing HKLM registry keys
- Wiping system files
