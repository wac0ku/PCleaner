# PCleaner TUI — User Guide

> Terminal UI powered by [Textual](https://textual.textualize.io/)  
> Launch: `python -m pcleaner --tui` or `pcleaner --tui`

---

## Layout

```
┌─ Header (clock + title) ────────────────────────────────────────────────┐
│ PCleaner — the free Cleaner App  ✓ Open Source  ✓ MIT                  │
├──────────────┬──────────────────────────────────────────────────────────┤
│  PCleaner    │                                                          │
│  v1.x.x      │                   Content Area                          │
│  ─ Nav ────  │        (changes based on selected screen)               │
│  🏠 Dashboard│                                                          │
│  🧹 Cleaner  │                                                          │
│  🗂 Registry │                                                          │
│  🚀 Startup  │                                                          │
│  📦 Uninstall│                                                          │
│  💽 Disk     │                                                          │
│  🔍 Dupes    │                                                          │
│  ❤ Health   │                                                          │
│  🛡 Task Mgr │                                                          │
│  ─ Actions ─ │                                                          │
│  ⚡ Flush DNS│                                                          │
│  📎 Clipboard│                                                          │
│  ─ Privileges│                                                          │
│  ⚠ Limited  │                                                          │
│  🛡 As Admin │                                                          │
├──────────────┴──────────────────────────────────────────────────────────┤
│ Footer: keyboard shortcuts                                              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1` | Go to Dashboard |
| `2` | Go to Cleaner |
| `3` | Go to Registry |
| `4` | Go to Startup |
| `5` | Go to Uninstaller |
| `6` | Go to Disk Analyzer |
| `7` | Go to Duplicates Finder |
| `8` | Go to Health |
| `9` | Go to Task Manager |
| `↑` / `↓` | Cycle through sidebar items (wraps around) |
| `F1`–`F9` | Same as `1`–`9` (legacy fallback) |
| `q` | Quit |
| `Ctrl+C` | Force quit |

---

## Screens

### 1 — Dashboard
Live system overview with real-time metrics.

- **CPU / RAM / Swap gauges** — color-coded: green (<70%), yellow (<90%), red (>90%)
- **Drive usage bars** — per-drive free/used breakdown
- **Info cards** — OS name, CPU model/cores, uptime, process count, startup program count, primary disk
- **Quick Scan** — press `⚡ Quick Scan` to estimate reclaimable space per category
- **Recommendations** — automatic health suggestions (e.g., "High RAM usage", "Low disk space")
- **Refresh** button — reloads all live data

### 2 — Cleaner
Scan and delete junk files.

1. Press **🔍 Analyze** — scans all junk categories (Temp Files, Browser Cache, Windows Update cache, Recycle Bin, etc.)
2. All found items are selected by default. Use **☑ Select All** / **☐ Deselect** or click rows to toggle.
3. Press **🧹 Clean** — shows a confirmation dialog. Confirm to permanently delete selected items.
4. Progress bar and log show real-time status. Final message shows freed space.

**Columns:** Category · Subcategory · Size · Admin required (⬤) · Safe (✓/⚠)

### 3 — Registry
Scan Windows registry for orphaned or broken entries.

1. Press **🔍 Scan** — scans HKCU Run keys, uninstall entries, class handlers.
2. Review issues in the table (type, key path, description).
3. Press **🧹 Clean** — auto-backs up to `%APPDATA%\PCleaner\backups\` then removes selected issues.
4. Press **💾 Backup** to export a `.reg` file without cleaning.

### 4 — Startup
Manage programs that run on Windows startup.

- Lists entries from `HKCU\...\Run`, `HKLM\...\Run`, and Task Scheduler.
- **Enable / Disable** — toggle without deleting (uses `DisabledRun` key).
- **Delete** — permanently removes the entry.
- Runs entirely in-session (no reboot required for changes to take effect).

### 5 — Uninstaller
Batch uninstall installed programs.

1. Press **🔄 Refresh** to list all installed programs from HKLM+HKCU Uninstall keys.
2. Click rows or use **☑ Select All** to choose programs.
3. Press **🗑 Uninstall Selected** — runs each program's `UninstallString` with confirmation.

**Note:** Some uninstallers open their own GUI window.

### 6 — Disk Analyzer
Analyze disk usage by file type and find largest directories.

1. Enter or browse a folder path (defaults to `C:\Users\<you>`).
2. Press **🔍 Analyze** — scans recursively.
3. Results show category breakdown (Images, Videos, Documents, Archives, Code, Other) with sizes.
4. **Largest directories** panel shows the top directories by size.

### 7 — Duplicates
Find duplicate files using MD5 hashing.

1. Enter folder path(s) or browse.
2. Press **🔍 Scan** — groups files by (size, hash) for efficiency.
3. Results show duplicate groups with paths and sizes.
4. Select duplicates to delete and press **🗑 Delete Selected**.

**Tip:** Always keep at least one copy per group — select wisely.

### 8 — Health
Comprehensive system health report.

- CPU usage, RAM, Swap memory
- Disk health summary per drive
- Running process count
- Startup program count
- Automatic recommendations (e.g., "Low disk on C:", "High CPU usage")

### 9 — Task Manager
Live process overview.

1. Press **🔄 Refresh** to list running processes.
2. Table shows: PID, Name, CPU%, Memory.
3. Select a process and press **⛔ Kill Process** to terminate it (with confirmation).
4. Use the search/filter input to find processes by name.

---

## Quick Actions (Sidebar)

| Button | Effect |
|--------|--------|
| ⚡ Flush DNS | Runs `ipconfig /flushdns` — clears DNS resolver cache |
| 📎 Clear Clipboard | Clears Windows clipboard contents |

Both show a toast notification on completion.

---

## Admin Elevation

The sidebar shows your current privilege level:

- **`✓ Running as Admin`** (green) — full access to all features
- **`⚠ Limited privileges`** + **`🛡 Run as Admin`** button — restricted mode

Pressing **Run as Admin**:
1. Shows a confirmation dialog.
2. On confirm, triggers Windows UAC elevation prompt.
3. If approved, PCleaner re-launches with full administrator rights.
4. If declined or cancelled, nothing happens.

**Features requiring admin:**
- Windows Prefetch cleaning (`C:\Windows\Prefetch`)
- Software Distribution cache (`C:\Windows\SoftwareDistribution\Download`)
- HKLM registry cleaning
- System-level startup entries
- Killing protected processes

---

## Tips

- Use `↑`/`↓` arrows to browse screens without lifting your hands from the keyboard.
- The Cleaner remembers your selection until you navigate away — you can deselect categories before cleaning.
- Registry backup files are saved automatically before any registry operation.
- Run PCleaner with `--dry-run` flag via CLI to preview what would be cleaned without deleting anything.
