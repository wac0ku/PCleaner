"""PCleaner GUI — built with CustomTkinter."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from pcleaner import APP_FULL_NAME, __version__
from pcleaner.utils.config import cfg

# ── Theme ──────────────────────────────────────────────────────────────────
ctk.set_appearance_mode(cfg.get("theme", "dark"))
ctk.set_default_color_theme("blue")

ACCENT   = "#2f9fe8"
SUCCESS  = "#2ecc71"
WARNING  = "#f39c12"
DANGER   = "#e74c3c"
BG_DARK  = "#1a1a2e"
BG_MID   = "#16213e"
BG_CARD  = "#0f3460"
TEXT     = "#e2e2e2"
TEXT_DIM = "#888888"

NAV_ITEMS = [
    ("Health",      "󰍛", "health"),
    ("Cleaner",     "󰃢", "cleaner"),
    ("Registry",    "󰙅", "registry"),
    ("Startup",     "󰐾", "startup"),
    ("Uninstaller", "󰆴", "uninstaller"),
    ("Disk",        "󰋊", "disk"),
    ("Duplicates",  "󱗸", "duplicates"),
    ("Wiper",       "󰒿", "wiper"),
    ("Settings",    "󰒓", "settings"),
]


def _fmt(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n //= 1024
    return f"{n:.1f} TB"


# ── Base frame helper ───────────────────────────────────────────────────────

class BaseView(ctk.CTkFrame):
    """Base class for all view panels."""

    def __init__(self, master, **kw):
        super().__init__(master, fg_color="transparent", **kw)

    def _title(self, text: str, subtitle: str = "") -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(self, text=text, font=ctk.CTkFont(size=22, weight="bold"))
        lbl.pack(anchor="w", padx=4, pady=(8, 0))
        if subtitle:
            sub = ctk.CTkLabel(self, text=subtitle,
                               font=ctk.CTkFont(size=12), text_color=TEXT_DIM)
            sub.pack(anchor="w", padx=4, pady=(0, 8))
        return lbl

    def _card(self, parent=None) -> ctk.CTkFrame:
        p = parent or self
        card = ctk.CTkFrame(p, corner_radius=10)
        card.pack(fill="x", padx=4, pady=4)
        return card

    def _run_thread(self, fn: Callable, *args) -> None:
        threading.Thread(target=fn, args=args, daemon=True).start()

    def _progress_bar(self, parent=None) -> ctk.CTkProgressBar:
        p = parent or self
        bar = ctk.CTkProgressBar(p, mode="determinate")
        bar.set(0)
        bar.pack(fill="x", padx=4, pady=4)
        return bar

    def _log_box(self, parent=None, height: int = 120) -> ctk.CTkTextbox:
        p = parent or self
        box = ctk.CTkTextbox(p, height=height, font=ctk.CTkFont(family="Consolas", size=11),
                             state="disabled")
        box.pack(fill="x", padx=4, pady=4)
        return box

    def _append_log(self, box: ctk.CTkTextbox, msg: str) -> None:
        box.configure(state="normal")
        box.insert("end", msg + "\n")
        box.see("end")
        box.configure(state="disabled")

    def _button_row(self, parent=None) -> ctk.CTkFrame:
        p = parent or self
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x", padx=4, pady=(4, 0))
        return row

    def _btn(self, parent: ctk.CTkFrame, text: str, cmd: Callable,
             color: str = ACCENT, text_color: str = "white") -> ctk.CTkButton:
        b = ctk.CTkButton(parent, text=text, command=cmd,
                          fg_color=color, hover_color=color,
                          text_color=text_color, corner_radius=8,
                          font=ctk.CTkFont(size=13, weight="bold"))
        b.pack(side="left", padx=4)
        return b


# ── Cleaner View ────────────────────────────────────────────────────────────

class CleanerView(BaseView):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._items: list = []
        self._vars:  list[tk.BooleanVar] = []
        self._build()

    def _build(self):
        self._title("Custom Cleaner", "Select categories and clean junk files from your system")

        # Buttons
        row = self._button_row()
        self._btn_analyze = self._btn(row, "  Analyze", self._analyze)
        self._btn_clean   = self._btn(row, "  Clean",   self._clean,   DANGER)
        self._btn_all     = self._btn(row, "Select All",    self._sel_all,    BG_CARD)
        self._btn_none    = self._btn(row, "Deselect All",  self._sel_none,   BG_CARD)

        # Progress + status
        self._bar = self._progress_bar()
        self._status = ctk.CTkLabel(self, text="Press Analyze to scan your system.",
                                    font=ctk.CTkFont(size=12), text_color=TEXT_DIM)
        self._status.pack(anchor="w", padx=8)

        # Scrollable checklist
        self._scroll = ctk.CTkScrollableFrame(self, height=280, label_text="Items Found")
        self._scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # Total label
        self._total_lbl = ctk.CTkLabel(self, text="",
                                       font=ctk.CTkFont(size=14, weight="bold"),
                                       text_color=WARNING)
        self._total_lbl.pack(anchor="w", padx=8, pady=(0, 4))

        # Log
        self._log = self._log_box()

    def _analyze(self):
        self._btn_analyze.configure(state="disabled")
        self._bar.configure(mode="indeterminate")
        self._bar.start()
        self._items.clear()
        self._vars.clear()
        for w in self._scroll.winfo_children():
            w.destroy()
        self._run_thread(self._do_scan)

    def _do_scan(self):
        from pcleaner.core.scanner import Scanner
        scanner = Scanner()

        def cb(label, cur, tot):
            self.after(0, self._status.configure, {"text": f"Scanning {label}..."})

        scanner.set_progress_callback(cb)
        result = scanner.scan_all()
        self._items = result.items

        self.after(0, self._populate_list, result)

    def _populate_list(self, result):
        self._bar.stop()
        self._bar.configure(mode="determinate")
        self._bar.set(1.0)
        self._vars.clear()
        for w in self._scroll.winfo_children():
            w.destroy()

        by_cat = result.by_category()
        for cat, items in sorted(by_cat.items()):
            # Category header
            hdr = ctk.CTkLabel(self._scroll, text=f"  {cat}",
                               font=ctk.CTkFont(size=13, weight="bold"),
                               text_color=ACCENT)
            hdr.pack(anchor="w", pady=(6, 0))
            for item in items:
                var = tk.BooleanVar(value=True)
                self._vars.append((var, item))
                row = ctk.CTkFrame(self._scroll, fg_color="transparent")
                row.pack(fill="x", padx=4)
                cb_w = ctk.CTkCheckBox(row, text=f"{item.subcategory}",
                                       variable=var, command=self._update_total,
                                       font=ctk.CTkFont(size=12))
                cb_w.pack(side="left")
                size_lbl = ctk.CTkLabel(row, text=item.size_str,
                                        font=ctk.CTkFont(size=12), text_color=WARNING)
                size_lbl.pack(side="right", padx=8)
                if item.requires_admin:
                    adm = ctk.CTkLabel(row, text="[admin]",
                                       font=ctk.CTkFont(size=10), text_color=DANGER)
                    adm.pack(side="right")

        self._update_total()
        self._status.configure(
            text=f"Found {result.item_count} items — {result.total_size_str} to clean"
        )
        self._btn_analyze.configure(state="normal")
        self._append_log(self._log, f"[Scan] {result.item_count} items, {result.total_size_str}")

    def _update_total(self):
        total = sum(item.size for var, item in self._vars if var.get())
        self._total_lbl.configure(text=f"Selected: {_fmt(total)}")

    def _sel_all(self):
        for var, _ in self._vars: var.set(True)
        self._update_total()

    def _sel_none(self):
        for var, _ in self._vars: var.set(False)
        self._update_total()

    def _clean(self):
        selected = [item for var, item in self._vars if var.get()]
        if not selected:
            messagebox.showinfo("PCleaner", "No items selected.")
            return
        total_str = _fmt(sum(i.size for i in selected))
        if not messagebox.askyesno("Confirm Clean",
                                   f"Delete {len(selected)} items ({total_str})?\n\nThis cannot be undone."):
            return
        self._btn_clean.configure(state="disabled")
        self._bar.set(0)
        self._run_thread(self._do_clean, selected)

    def _do_clean(self, selected):
        from pcleaner.core.cleaner import Cleaner
        from pcleaner.core.scanner import ScanResult
        cleaner = Cleaner()
        total = len(selected)

        def cb(item, cur, tot):
            self.after(0, self._bar.set, cur / max(tot, 1))
            self.after(0, self._status.configure,
                       {"text": f"Cleaning {item.subcategory}... ({cur}/{tot})"})

        cleaner.set_progress_callback(cb)
        result = cleaner.clean(ScanResult(items=selected))
        self.after(0, self._on_clean_done, result)

    def _on_clean_done(self, result):
        self._bar.set(1.0)
        self._btn_clean.configure(state="normal")
        self._status.configure(text=f"Done! Freed {result.freed_str}")
        self._append_log(self._log,
            f"[Clean] Freed {result.freed_str}  |  "
            f"{len(result.errors)} errors  |  {len(result.skipped)} skipped (admin)")
        messagebox.showinfo("PCleaner", f"Cleaning complete!\nFreed: {result.freed_str}")
        for w in self._scroll.winfo_children(): w.destroy()
        self._vars.clear()
        self._total_lbl.configure(text="")


# ── Registry View ───────────────────────────────────────────────────────────

class RegistryView(BaseView):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._issues: list = []
        self._vars:   list = []
        self._build()

    def _build(self):
        self._title("Registry Cleaner", "Scans for invalid registry entries — auto-backup before cleaning")
        row = self._button_row()
        self._btn(row, "Scan Registry", self._scan)
        self._btn(row, "Clean Selected", self._clean, DANGER)

        self._bar    = self._progress_bar()
        self._status = ctk.CTkLabel(self, text="Press Scan to analyse the registry.",
                                    font=ctk.CTkFont(size=12), text_color=TEXT_DIM)
        self._status.pack(anchor="w", padx=8)

        self._scroll = ctk.CTkScrollableFrame(self, height=300, label_text="Issues Found")
        self._scroll.pack(fill="both", expand=True, padx=4, pady=4)
        self._log = self._log_box()

    def _scan(self):
        self._bar.configure(mode="indeterminate"); self._bar.start()
        for w in self._scroll.winfo_children(): w.destroy()
        self._issues.clear(); self._vars.clear()
        self._run_thread(self._do_scan)

    def _do_scan(self):
        from pcleaner.core.registry import RegistryScanner
        def cb(label, cur, tot):
            self.after(0, self._status.configure, {"text": f"Checking {label}..."})
        issues = RegistryScanner().scan(progress_cb=cb)
        self._issues = issues
        self.after(0, self._populate, issues)

    def _populate(self, issues):
        self._bar.stop(); self._bar.configure(mode="determinate"); self._bar.set(1.0)
        for w in self._scroll.winfo_children(): w.destroy()
        self._vars.clear()
        for issue in issues:
            var = tk.BooleanVar(value=True)
            self._vars.append((var, issue))
            row = ctk.CTkFrame(self._scroll, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=1)
            ctk.CTkCheckBox(row, text=f"[{issue.issue_type}]  {issue.description[:60]}",
                            variable=var, font=ctk.CTkFont(size=11)).pack(side="left")
            ctk.CTkLabel(row, text=issue.full_path[:40],
                         font=ctk.CTkFont(size=10), text_color=TEXT_DIM).pack(side="right", padx=4)
        self._status.configure(text=f"Found {len(issues)} registry issues")
        self._append_log(self._log, f"[Registry Scan] {len(issues)} issues found")

    def _clean(self):
        selected = [issue for var, issue in self._vars if var.get()]
        if not selected:
            messagebox.showinfo("PCleaner", "No issues selected."); return
        if not messagebox.askyesno("Confirm",
            f"Clean {len(selected)} registry entries?\n\nA .reg backup will be created first."):
            return
        self._run_thread(self._do_clean, selected)

    def _do_clean(self, selected):
        from pcleaner.core.registry import RegistryCleaner
        cleaner = RegistryCleaner()
        backup = cleaner.backup_full()
        cleaned, errors = cleaner.clean(selected)
        msg = f"[Registry Clean] Cleaned: {cleaned}  |  Errors: {errors}"
        if backup:
            msg += f"\n  Backup: {backup}"
        self.after(0, self._append_log, self._log, msg)
        self.after(0, messagebox.showinfo, "PCleaner", f"Cleaned {cleaned} entries.\n{errors} errors.")
        self.after(0, self._scan)


# ── Startup View ────────────────────────────────────────────────────────────

class StartupView(BaseView):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._entries: list = []
        self._build()

    def _build(self):
        self._title("Startup Manager", "Control programs that launch when Windows starts")
        row = self._button_row()
        self._btn(row, "Refresh",  self._refresh)
        self._btn(row, "Disable",  self._disable, WARNING)
        self._btn(row, "Enable",   self._enable,  SUCCESS)
        self._btn(row, "Delete",   self._delete,  DANGER)

        # Listbox with scrollbar
        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=4, pady=4)
        self._listbox = tk.Listbox(frame, bg="#1e1e2e", fg=TEXT,
                                   selectbackground=ACCENT, selectforeground="white",
                                   font=("Consolas", 11), bd=0, relief="flat",
                                   activestyle="none")
        scrollbar = ctk.CTkScrollbar(frame, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._listbox.pack(fill="both", expand=True)

        self._log = self._log_box()
        self._refresh()

    def _refresh(self):
        self._run_thread(self._load)

    def _load(self):
        from pcleaner.tools.startup import StartupManager
        entries = StartupManager().list_entries()
        self._entries = entries
        self.after(0, self._populate, entries)

    def _populate(self, entries):
        self._listbox.delete(0, "end")
        for e in entries:
            status = "ON " if e.enabled else "OFF"
            line = f"  [{status}]  {e.name:<30}  {e.source:<15}  {e.command[:40]}"
            self._listbox.insert("end", line)
            self._listbox.itemconfig("end", fg=TEXT if e.enabled else TEXT_DIM)

    def _selected_entry(self):
        sel = self._listbox.curselection()
        if not sel: messagebox.showinfo("PCleaner", "Select an entry first."); return None
        return self._entries[sel[0]]

    def _disable(self):
        e = self._selected_entry()
        if not e: return
        from pcleaner.tools.startup import StartupManager
        ok = StartupManager().disable(e)
        self._append_log(self._log, f"[Startup] {'Disabled' if ok else 'FAILED'}: {e.name}")
        if ok: self._refresh()

    def _enable(self):
        e = self._selected_entry()
        if not e: return
        from pcleaner.tools.startup import StartupManager
        ok = StartupManager().enable(e)
        self._append_log(self._log, f"[Startup] {'Enabled' if ok else 'FAILED'}: {e.name}")
        if ok: self._refresh()

    def _delete(self):
        e = self._selected_entry()
        if not e: return
        if not messagebox.askyesno("Confirm", f"Permanently delete startup entry '{e.name}'?"): return
        from pcleaner.tools.startup import StartupManager
        ok = StartupManager().delete(e)
        self._append_log(self._log, f"[Startup] {'Deleted' if ok else 'FAILED'}: {e.name}")
        if ok: self._refresh()


# ── Uninstaller View ────────────────────────────────────────────────────────

class UninstallerView(BaseView):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._programs: list = []
        self._filtered: list = []
        self._build()

    def _build(self):
        self._title("Software Uninstaller", "Browse and remove installed programs")

        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.pack(fill="x", padx=4, pady=4)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        ctk.CTkEntry(search_row, textvariable=self._search_var,
                     placeholder_text="Search programs...",
                     font=ctk.CTkFont(size=13)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._btn(search_row, "Refresh", self._refresh)

        row = self._button_row()
        self._btn(row, "Uninstall Selected", self._uninstall, DANGER)

        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=4, pady=4)
        self._listbox = tk.Listbox(frame, bg="#1e1e2e", fg=TEXT,
                                   selectbackground=ACCENT, selectforeground="white",
                                   font=("Consolas", 11), bd=0, relief="flat")
        scrollbar = ctk.CTkScrollbar(frame, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._listbox.pack(fill="both", expand=True)

        self._status = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12), text_color=TEXT_DIM)
        self._status.pack(anchor="w", padx=8)
        self._log = self._log_box()
        self._refresh()

    def _refresh(self):
        self._status.configure(text="Loading...")
        self._run_thread(self._load)

    def _load(self):
        from pcleaner.tools.uninstaller import Uninstaller
        programs = Uninstaller().list_programs()
        self._programs = programs
        self._filtered = programs
        self.after(0, self._populate, programs)

    def _populate(self, programs):
        self._listbox.delete(0, "end")
        for p in programs:
            line = f"  {p.name:<45}  {p.version:<12}  {p.size_str:<10}  {p.publisher[:30]}"
            self._listbox.insert("end", line)
        self._status.configure(text=f"{len(programs)} programs installed")

    def _on_search(self, *_):
        q = self._search_var.get().lower()
        self._filtered = ([p for p in self._programs if q in p.name.lower() or q in p.publisher.lower()]
                          if q else self._programs)
        self._populate(self._filtered)

    def _uninstall(self):
        sel = self._listbox.curselection()
        if not sel: messagebox.showinfo("PCleaner", "Select a program first."); return
        prog = self._filtered[sel[0]]
        if not messagebox.askyesno("Confirm Uninstall",
                                   f"Uninstall '{prog.name}'?\n\nThis will launch its uninstaller."): return
        from pcleaner.tools.uninstaller import Uninstaller
        ok = Uninstaller().uninstall(prog)
        self._append_log(self._log,
            f"[Uninstall] {'Launched uninstaller for' if ok else 'FAILED:'} {prog.name}")


# ── Disk Analyzer View ──────────────────────────────────────────────────────

class DiskView(BaseView):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._build()

    def _build(self):
        self._title("Disk Analyzer", "Breakdown of disk usage by file type")

        path_row = ctk.CTkFrame(self, fg_color="transparent")
        path_row.pack(fill="x", padx=4, pady=4)
        self._path_var = tk.StringVar(value=str(Path.home()))
        ctk.CTkEntry(path_row, textvariable=self._path_var,
                     font=ctk.CTkFont(size=12)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._btn(path_row, "Browse", self._browse)
        self._btn(path_row, "Analyze", self._analyze)

        self._bar    = self._progress_bar()
        self._status = ctk.CTkLabel(self, text="Choose a folder and press Analyze.",
                                    font=ctk.CTkFont(size=12), text_color=TEXT_DIM)
        self._status.pack(anchor="w", padx=8)

        # Results — use scrollable frame
        self._scroll = ctk.CTkScrollableFrame(self, height=350, label_text="File Type Breakdown")
        self._scroll.pack(fill="both", expand=True, padx=4, pady=4)

    def _browse(self):
        d = filedialog.askdirectory(title="Select folder to analyze")
        if d: self._path_var.set(d)

    def _analyze(self):
        path = Path(self._path_var.get())
        if not path.exists():
            messagebox.showerror("PCleaner", "Path does not exist."); return
        for w in self._scroll.winfo_children(): w.destroy()
        self._bar.configure(mode="indeterminate"); self._bar.start()
        self._status.configure(text="Analyzing…")
        self._run_thread(self._do_analyze, path)

    def _do_analyze(self, path):
        from pcleaner.tools.disk_analyzer import DiskAnalyzer
        analyzer = DiskAnalyzer()
        result = analyzer.analyze(path)
        self.after(0, self._show_results, result)

    def _show_results(self, result):
        self._bar.stop(); self._bar.configure(mode="determinate"); self._bar.set(1.0)
        for w in self._scroll.winfo_children(): w.destroy()

        for cat in result.sorted_categories():
            if cat.size == 0: continue
            pct = result.percent(cat.name)
            row = ctk.CTkFrame(self._scroll, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=2)
            ctk.CTkLabel(row, text=f"{cat.name:<14}", font=ctk.CTkFont(size=12),
                         width=120).pack(side="left")
            bar = ctk.CTkProgressBar(row, width=200)
            bar.set(pct / 100)
            bar.pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f"{cat.size_str:>9}  {pct:5.1f}%",
                         font=ctk.CTkFont(family="Consolas", size=12),
                         text_color=WARNING).pack(side="left", padx=4)

        self._status.configure(
            text=f"Total: {result.total_size_str}  |  {result.total_files} files"
        )


# ── Duplicates View ─────────────────────────────────────────────────────────

class DuplicatesView(BaseView):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._groups: list = []
        self._build()

    def _build(self):
        self._title("Duplicate File Finder", "Find and remove duplicate files using MD5 hashing")

        path_row = ctk.CTkFrame(self, fg_color="transparent")
        path_row.pack(fill="x", padx=4, pady=4)
        self._path_var = tk.StringVar(value=str(Path.home()))
        ctk.CTkEntry(path_row, textvariable=self._path_var,
                     font=ctk.CTkFont(size=12)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._btn(path_row, "Browse", self._browse)
        self._btn(path_row, "Scan",   self._scan)

        row = self._button_row()
        self._btn(row, "Delete Duplicates (keep newest)", self._delete, DANGER)

        self._bar    = self._progress_bar()
        self._status = ctk.CTkLabel(self, text="Choose a folder and press Scan.",
                                    font=ctk.CTkFont(size=12), text_color=TEXT_DIM)
        self._status.pack(anchor="w", padx=8)

        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=4, pady=4)
        cols = ("#", "Files", "Size Each", "Wasted", "Example")
        self._tree = _make_tree(frame, cols)
        self._log = self._log_box()

    def _browse(self):
        d = filedialog.askdirectory()
        if d: self._path_var.set(d)

    def _scan(self):
        path = Path(self._path_var.get())
        if not path.exists():
            messagebox.showerror("PCleaner", "Path does not exist."); return
        self._tree.delete(*self._tree.get_children())
        self._bar.configure(mode="indeterminate"); self._bar.start()
        self._run_thread(self._do_scan, path)

    def _do_scan(self, path):
        from pcleaner.tools.duplicates import DuplicateFinder
        def cb(phase, cur, tot):
            self.after(0, self._status.configure, {"text": f"{phase}: {cur}…"})
        finder = DuplicateFinder()
        finder.set_progress_callback(cb)
        result = finder.scan([path])
        self._groups = result.groups
        self.after(0, self._show_results, result)

    def _show_results(self, result):
        self._bar.stop(); self._bar.configure(mode="determinate"); self._bar.set(1.0)
        self._tree.delete(*self._tree.get_children())
        for i, g in enumerate(result.sorted_by_wasted(), 1):
            self._tree.insert("", "end", values=(
                i, len(g.files), g.size_str, g.wasted_str, str(g.files[0])[:55]
            ))
        self._status.configure(
            text=f"{len(result.groups)} duplicate groups  |  {result.total_wasted_str} wasted"
        )
        self._append_log(self._log,
            f"[Duplicates] {len(result.groups)} groups, {result.total_wasted_str} wasted, "
            f"{result.scanned_files} files scanned")

    def _delete(self):
        if not self._groups:
            messagebox.showinfo("PCleaner", "Run a scan first."); return
        wasted = _fmt(sum(g.wasted_bytes for g in self._groups))
        if not messagebox.askyesno("Confirm Delete",
            f"Delete {sum(len(g.files)-1 for g in self._groups)} duplicate files?\n"
            f"Frees {wasted}. Keeps the newest copy."): return
        self._run_thread(self._do_delete)

    def _do_delete(self):
        from pcleaner.tools.duplicates import DuplicateFinder
        deleted, errors = DuplicateFinder().delete_duplicates(self._groups, keep="newest")
        self.after(0, self._append_log, self._log,
                   f"[Duplicates] Deleted {deleted}  |  Errors: {errors}")
        self.after(0, messagebox.showinfo, "PCleaner", f"Deleted {deleted} files.\n{errors} errors.")
        self._groups = []
        self.after(0, self._tree.delete, *self._tree.get_children())


# ── Wiper View ──────────────────────────────────────────────────────────────

class WiperView(BaseView):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._build()

    def _build(self):
        self._title("Drive Wiper", "Securely overwrite files so they cannot be recovered")

        card = self._card()
        card.columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Target:", font=ctk.CTkFont(size=13)).grid(
            row=0, column=0, padx=8, pady=8, sticky="w")
        self._path_var = tk.StringVar()
        ctk.CTkEntry(card, textvariable=self._path_var,
                     font=ctk.CTkFont(size=12)).grid(row=0, column=1, padx=4, pady=8, sticky="ew")
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=0, column=2, padx=4)
        self._btn(btn_row, "File",   self._browse_file)
        self._btn(btn_row, "Folder", self._browse_dir)

        ctk.CTkLabel(card, text="Passes:", font=ctk.CTkFont(size=13)).grid(
            row=1, column=0, padx=8, pady=8, sticky="w")
        self._passes_var = tk.StringVar(value="3")
        passes_menu = ctk.CTkOptionMenu(
            card, values=["1 — Simple", "3 — DoD 3-pass", "7 — DoD 7-pass", "35 — Gutmann"],
            variable=self._passes_var, font=ctk.CTkFont(size=12))
        passes_menu.grid(row=1, column=1, padx=4, pady=8, sticky="w")

        ctk.CTkLabel(card, text="Mode:", font=ctk.CTkFont(size=13)).grid(
            row=2, column=0, padx=8, pady=8, sticky="w")
        self._mode_var = tk.StringVar(value="File/Folder")
        mode_menu = ctk.CTkOptionMenu(
            card, values=["File/Folder", "Free Space"],
            variable=self._mode_var, font=ctk.CTkFont(size=12))
        mode_menu.grid(row=2, column=1, padx=4, pady=8, sticky="w")

        row = self._button_row()
        self._btn(row, "  Wipe Now", self._wipe, DANGER)

        self._bar    = self._progress_bar()
        self._status = ctk.CTkLabel(self, text="",
                                    font=ctk.CTkFont(size=12), text_color=TEXT_DIM)
        self._status.pack(anchor="w", padx=8)
        self._log = self._log_box()

    def _browse_file(self):
        f = filedialog.askopenfilename()
        if f: self._path_var.set(f)

    def _browse_dir(self):
        d = filedialog.askdirectory()
        if d: self._path_var.set(d)

    def _wipe(self):
        path_str = self._path_var.get().strip()
        if not path_str:
            messagebox.showerror("PCleaner", "Choose a file or folder."); return
        path = Path(path_str)
        passes = int(self._passes_var.get().split(" ")[0])
        mode   = self._mode_var.get()

        msg = (f"Wipe FREE SPACE on drive {path}?" if mode == "Free Space"
               else f"PERMANENTLY DESTROY:\n{path}\n\nThis cannot be undone!")
        if not messagebox.askyesno("⚠ Confirm Wipe", msg, icon="warning"): return

        self._bar.configure(mode="indeterminate"); self._bar.start()
        self._status.configure(text="Wiping…")
        self._run_thread(self._do_wipe, path, passes, mode == "Free Space")

    def _do_wipe(self, path, passes, free_space):
        from pcleaner.core.wiper import DriveWiper
        wiper = DriveWiper(passes=passes)
        if free_space:
            ok = wiper.wipe_free_space(str(path))
        elif path.is_file():
            ok = wiper.wipe_file(path)
        else:
            wiped, failed = wiper.wipe_directory(path)
            ok = failed == 0
        self.after(0, self._bar.stop)
        self.after(0, self._bar.configure, {"mode": "determinate"})
        self.after(0, self._bar.set, 1.0 if ok else 0.0)
        self.after(0, self._status.configure, {"text": "Wipe complete." if ok else "Wipe failed."})
        self.after(0, self._append_log, self._log,
                   f"[Wipe] {'OK' if ok else 'FAILED'}: {path}  ({passes}-pass)")
        self.after(0, messagebox.showinfo if ok else messagebox.showerror,
                   "PCleaner", "Wipe complete!" if ok else "Wipe failed.")


# ── Health View ─────────────────────────────────────────────────────────────

class HealthView(BaseView):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._build()
        self._refresh()

    def _build(self):
        self._title("System Health", "Live overview of your system performance and status")
        row = self._button_row()
        self._btn(row, "Refresh", self._refresh)

        self._scroll = ctk.CTkScrollableFrame(self, height=420)
        self._scroll.pack(fill="both", expand=True, padx=4, pady=4)

    def _refresh(self):
        for w in self._scroll.winfo_children(): w.destroy()
        ctk.CTkLabel(self._scroll, text="Loading…",
                     font=ctk.CTkFont(size=13), text_color=TEXT_DIM).pack()
        self._run_thread(self._load)

    def _load(self):
        from pcleaner.tools.health import HealthChecker
        report = HealthChecker().check()
        self.after(0, self._show, report)

    def _show(self, report):
        for w in self._scroll.winfo_children(): w.destroy()

        def _card_row(card, label: str, value: str, color: str = TEXT):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=1)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12),
                         text_color=TEXT_DIM, width=150, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=ctk.CTkFont(size=12),
                         text_color=color).pack(side="left", padx=4)

        def _section(title: str) -> ctk.CTkFrame:
            ctk.CTkLabel(self._scroll, text=title,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=ACCENT).pack(anchor="w", padx=4, pady=(10, 2))
            card = ctk.CTkFrame(self._scroll, corner_radius=10)
            card.pack(fill="x", padx=4, pady=2)
            return card

        # System
        sys_card = _section("System")
        _card_row(sys_card, "OS",        report.os_name[:50])
        _card_row(sys_card, "Hostname",  report.hostname)
        _card_row(sys_card, "Uptime",    report.uptime_str)

        # CPU
        cpu_card = _section("CPU")
        _card_row(cpu_card, "Processor", report.cpu_brand[:50])
        _card_row(cpu_card, "Cores",     f"{report.cpu_cores} physical / {report.cpu_threads} logical")
        cpu_color = DANGER if report.cpu_usage > 90 else WARNING if report.cpu_usage > 70 else SUCCESS
        _card_row(cpu_card, "Usage",     f"{report.cpu_usage:.1f}%", cpu_color)

        # RAM
        ram_card = _section("Memory")
        ram_color = DANGER if report.ram_percent > 90 else WARNING if report.ram_percent > 75 else SUCCESS
        _card_row(ram_card, "Total",     report.ram_total_str)
        _card_row(ram_card, "Used",      f"{report.ram_used_str}  ({report.ram_percent:.1f}%)", ram_color)
        _card_row(ram_card, "Free",      report.ram_free_str)
        ram_bar = ctk.CTkProgressBar(ram_card)
        ram_bar.set(report.ram_percent / 100)
        ram_bar.pack(fill="x", padx=8, pady=4)

        # Drives
        drv_card = _section("Drives")
        for d in report.drives:
            row = ctk.CTkFrame(drv_card, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=3)
            color = DANGER if d.percent_used > 90 else WARNING if d.percent_used > 75 else SUCCESS
            ctk.CTkLabel(row, text=d.drive, font=ctk.CTkFont(size=12),
                         width=60, anchor="w").pack(side="left")
            bar = ctk.CTkProgressBar(row, width=180)
            bar.set(d.percent_used / 100)
            bar.pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f"{d.used_str} / {d.total_str}  ({d.percent_used:.0f}%)",
                         font=ctk.CTkFont(size=11), text_color=color).pack(side="left", padx=4)

        # Startup
        _card_row(_section("Startup"), "Programs at startup",
                  str(report.startup_count),
                  WARNING if report.startup_count > 15 else TEXT)

        # Recommendations
        if report.recommendations:
            rec_card = _section("Recommendations")
            for rec in report.recommendations:
                ctk.CTkLabel(rec_card, text=f"  •  {rec}",
                             font=ctk.CTkFont(size=12), text_color=WARNING,
                             wraplength=600, anchor="w", justify="left").pack(
                    anchor="w", padx=8, pady=2)


# ── Settings View ───────────────────────────────────────────────────────────

class SettingsView(BaseView):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._build()

    def _build(self):
        self._title("Settings", "Configure PCleaner behaviour")
        card = self._card()

        def _row(label: str, widget_fn: Callable) -> None:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=6)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13),
                         width=200, anchor="w").pack(side="left")
            widget_fn(row)

        # Theme
        self._theme_var = tk.StringVar(value=cfg.get("theme", "dark").title())
        _row("Appearance", lambda p: ctk.CTkOptionMenu(
            p, values=["Dark", "Light", "System"],
            variable=self._theme_var, command=self._change_theme,
            font=ctk.CTkFont(size=12)).pack(side="left"))

        # Confirm before clean
        self._confirm_var = tk.BooleanVar(value=cfg.get("confirm_before_clean", True))
        _row("Confirm before cleaning", lambda p: ctk.CTkSwitch(
            p, text="", variable=self._confirm_var,
            command=lambda: cfg.set("confirm_before_clean", self._confirm_var.get())
        ).pack(side="left"))

        # Registry backup
        self._backup_var = tk.BooleanVar(value=cfg.get("backup_registry", True))
        _row("Backup registry before cleaning", lambda p: ctk.CTkSwitch(
            p, text="", variable=self._backup_var,
            command=lambda: cfg.set("backup_registry", self._backup_var.get())
        ).pack(side="left"))

        # Wiper passes
        self._wiper_var = tk.StringVar(value=str(cfg.get("wiper_passes", 3)))
        _row("Default wiper passes", lambda p: ctk.CTkOptionMenu(
            p, values=["1", "3", "7", "35"],
            variable=self._wiper_var, command=lambda v: cfg.set("wiper_passes", int(v)),
            font=ctk.CTkFont(size=12)).pack(side="left"))

        info_card = self._card()
        ctk.CTkLabel(info_card, text=f"  {APP_FULL_NAME}  v{__version__}\n"
                     "  Open-source, MIT license.\n  Settings auto-saved.",
                     font=ctk.CTkFont(size=12), text_color=TEXT_DIM, justify="left").pack(
            anchor="w", padx=8, pady=8)

    def _change_theme(self, value: str):
        ctk.set_appearance_mode(value.lower())
        cfg.set("theme", value.lower())


# ── Treeview helper ─────────────────────────────────────────────────────────

def _make_tree(parent, columns: tuple) -> "ttk.Treeview":
    import tkinter.ttk as ttk
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Custom.Treeview",
                    background="#1e1e2e", foreground=TEXT,
                    fieldbackground="#1e1e2e", bordercolor="#333",
                    rowheight=24, font=("Consolas", 11))
    style.configure("Custom.Treeview.Heading",
                    background="#0f3460", foreground=ACCENT,
                    font=("Segoe UI", 11, "bold"), relief="flat")
    style.map("Custom.Treeview", background=[("selected", ACCENT)])

    frame = ctk.CTkFrame(parent)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=columns, show="headings", style="Custom.Treeview")
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120)
    vsb = ctk.CTkScrollbar(frame, command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)
    return tree


# ── Main Window ─────────────────────────────────────────────────────────────

class PCleaner(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title(f"{APP_FULL_NAME}  v{__version__}")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self._current_view: BaseView | None = None
        self._views: dict[str, BaseView] = {}
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ──
        self._sidebar = ctk.CTkFrame(self, width=190, corner_radius=0)
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_rowconfigure(20, weight=1)

        logo = ctk.CTkLabel(self._sidebar, text="PCleaner",
                             font=ctk.CTkFont(size=20, weight="bold"),
                             text_color=ACCENT)
        logo.grid(row=0, column=0, padx=16, pady=(20, 4))
        sub = ctk.CTkLabel(self._sidebar, text="the free Cleaner App",
                           font=ctk.CTkFont(size=10), text_color=TEXT_DIM)
        sub.grid(row=1, column=0, padx=16, pady=(0, 16))

        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        for i, (label, icon, key) in enumerate(NAV_ITEMS, start=2):
            btn = ctk.CTkButton(
                self._sidebar, text=f"  {label}",
                anchor="w", font=ctk.CTkFont(size=13),
                fg_color="transparent", text_color=TEXT_DIM,
                hover_color=("#2a2a3e", "#2a2a3e"),
                corner_radius=8, height=38,
                command=lambda k=key: self._show_view(k),
            )
            btn.grid(row=i, column=0, padx=8, pady=2, sticky="ew")
            self._nav_buttons[key] = btn

        # Version at bottom
        ctk.CTkLabel(self._sidebar, text=f"v{__version__}",
                     font=ctk.CTkFont(size=10), text_color=TEXT_DIM).grid(
            row=21, column=0, padx=16, pady=12)

        # ── Content area ──
        self._content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._content.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        # Pre-create all views
        VIEW_CLASSES = {
            "health":      HealthView,
            "cleaner":     CleanerView,
            "registry":    RegistryView,
            "startup":     StartupView,
            "uninstaller": UninstallerView,
            "disk":        DiskView,
            "duplicates":  DuplicatesView,
            "wiper":       WiperView,
            "settings":    SettingsView,
        }
        for key, cls in VIEW_CLASSES.items():
            view = cls(self._content)
            view.grid(row=0, column=0, sticky="nsew")
            self._views[key] = view

        self._show_view("health")

    def _show_view(self, key: str) -> None:
        # Deactivate old button
        if self._current_view:
            for k, btn in self._nav_buttons.items():
                btn.configure(fg_color="transparent", text_color=TEXT_DIM)

        view = self._views.get(key)
        if view:
            view.tkraise()
            self._current_view = view

        btn = self._nav_buttons.get(key)
        if btn:
            btn.configure(fg_color=("#1a3a5c", "#1a3a5c"), text_color=ACCENT)
