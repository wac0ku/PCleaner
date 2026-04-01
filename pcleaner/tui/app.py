"""PCleaner TUI — built with Textual."""

from __future__ import annotations

from pathlib import Path

# CSS lives next to this file regardless of CWD
_CSS_PATH = Path(__file__).parent / "pcleaner.tcss"

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    RichLog,
    TabbedContent,
    TabPane,
)

from pcleaner import APP_FULL_NAME, __version__


# ---------------------------------------------------------------------------
# Confirm modal
# ---------------------------------------------------------------------------

class ConfirmModal(ModalScreen):
    """A simple yes/no confirmation modal."""

    def __init__(self, message: str, title: str = "Confirm") -> None:
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Container(id="modal-dialog"):
            yield Label(self._title, id="modal-title")
            yield Label(self._message)
            with Horizontal(id="modal-buttons"):
                yield Button("Yes", id="btn-yes", variant="error")
                yield Button("No",  id="btn-no",  variant="default")

    @on(Button.Pressed, "#btn-yes")
    def confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn-no")
    def cancel(self) -> None:
        self.dismiss(False)


# ---------------------------------------------------------------------------
# Cleaner tab
# ---------------------------------------------------------------------------

class CleanerPane(TabPane):
    """Main cleaner tab: scan + clean junk files."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Custom Cleaner", classes="panel-title")
            yield Label("Select items to clean and press Analyze, then Clean.", classes="stat-label")
            with Horizontal(id="button-row"):
                yield Button("Analyze",      id="btn-analyze",  variant="primary")
                yield Button("Clean",        id="btn-clean",    variant="error")
                yield Button("Select All",   id="btn-select-all")
                yield Button("Deselect All", id="btn-deselect-all")
            yield ProgressBar(total=100, show_eta=False, id="cleaner-progress")
            yield Label("", id="scan-status", classes="stat-label")
            yield DataTable(id="cleaner-table", zebra_stripes=True)
            yield Label("", id="total-label", classes="size-value")
            with ScrollableContainer():
                yield RichLog(id="cleaner-log", highlight=True, markup=True)

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#cleaner-table")
        tbl.add_columns("✓", "Category", "Subcategory", "Size", "Admin", "Safe")
        self._items: list = []
        self._selected: set[int] = set()
        bar: ProgressBar = self.query_one("#cleaner-progress")
        bar.update(progress=0)

    @on(Button.Pressed, "#btn-analyze")
    def do_analyze(self) -> None:
        self._run_scan()

    @on(Button.Pressed, "#btn-clean")
    def do_clean(self) -> None:
        if not self._items:
            self.query_one("#cleaner-log", RichLog).write("[yellow]Run Analyze first.[/yellow]")
            return
        self.app.push_screen(
            ConfirmModal("This will permanently delete selected files. Continue?", "Confirm Clean"),
            self._on_confirm_clean,
        )

    def _on_confirm_clean(self, confirmed: bool) -> None:
        if confirmed:
            self._run_clean()

    @on(Button.Pressed, "#btn-select-all")
    def select_all(self) -> None:
        self._selected = set(range(len(self._items)))
        self._refresh_table()

    @on(Button.Pressed, "#btn-deselect-all")
    def deselect_all(self) -> None:
        self._selected.clear()
        self._refresh_table()

    @on(DataTable.RowSelected)
    def row_clicked(self, event: DataTable.RowSelected) -> None:
        row_idx = event.cursor_row
        if row_idx in self._selected:
            self._selected.discard(row_idx)
        else:
            self._selected.add(row_idx)
        self._refresh_table()

    def _refresh_table(self) -> None:
        tbl: DataTable = self.query_one("#cleaner-table")
        tbl.clear()
        for i, item in enumerate(self._items):
            check = "☑" if i in self._selected else "☐"
            admin = "[red]✓[/]" if item.requires_admin else ""
            safe  = "[green]✓[/]" if item.safe else "[yellow]⚠[/]"
            tbl.add_row(check, item.category, item.subcategory, item.size_str, admin, safe, key=str(i))
        total = sum(self._items[i].size for i in self._selected) if self._selected else sum(it.size for it in self._items)
        label: Label = self.query_one("#total-label")
        label.update(f"Total: {_fmt(total)}")

    @work(thread=True)
    def _run_scan(self) -> None:
        from pcleaner.core.scanner import Scanner, ScanResult
        self.app.call_from_thread(self._set_status, "Scanning...")
        bar: ProgressBar = self.query_one("#cleaner-progress")
        log_widget: RichLog = self.query_one("#cleaner-log")

        def on_progress(label: str, current: int, total: int) -> None:
            self.app.call_from_thread(bar.update, progress=int(current / max(total, 1) * 100))
            self.app.call_from_thread(self._set_status, f"Scanning {label}...")
            self.app.call_from_thread(log_widget.write, f"[dim]Scanning {label}...[/dim]")

        scanner = Scanner()
        scanner.set_progress_callback(on_progress)
        result = scanner.scan_all()
        self._items = result.items
        self._selected = set(range(len(self._items)))

        self.app.call_from_thread(self._refresh_table)
        self.app.call_from_thread(bar.update, progress=100)
        self.app.call_from_thread(
            self._set_status,
            f"Found {result.item_count} items — {result.total_size_str} to clean"
        )
        self.app.call_from_thread(
            log_widget.write,
            f"[green]Scan complete: {result.item_count} items, {result.total_size_str}[/green]"
        )

    @work(thread=True)
    def _run_clean(self) -> None:
        from pcleaner.core.cleaner import Cleaner
        from pcleaner.core.scanner import ScanResult
        log_widget: RichLog = self.query_one("#cleaner-log")
        bar: ProgressBar = self.query_one("#cleaner-progress")

        selected_items = [self._items[i] for i in sorted(self._selected)]
        if not selected_items:
            self.app.call_from_thread(log_widget.write, "[yellow]No items selected.[/yellow]")
            return

        cleaner = Cleaner()
        scan_result = ScanResult(items=selected_items)

        def on_progress(item, current: int, total: int) -> None:
            self.app.call_from_thread(bar.update, progress=int(current / max(total, 1) * 100))
            self.app.call_from_thread(
                log_widget.write, f"[dim]Cleaning {item.subcategory}...[/dim]"
            )

        cleaner.set_progress_callback(on_progress)
        result = cleaner.clean(scan_result)

        self.app.call_from_thread(
            log_widget.write,
            f"[green]✓ Done! Freed {result.freed_str}. "
            f"({len(result.errors)} errors, {len(result.skipped)} skipped)[/green]"
        )
        self.app.call_from_thread(self._set_status, f"Cleaned! Freed {result.freed_str}")
        self._items = []
        self._selected.clear()
        self.app.call_from_thread(self._refresh_table)

    def _set_status(self, msg: str) -> None:
        self.query_one("#scan-status", Label).update(msg)


# ---------------------------------------------------------------------------
# Registry tab
# ---------------------------------------------------------------------------

class RegistryPane(TabPane):
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Registry Cleaner", classes="panel-title")
            yield Label("Scans for orphaned registry entries. A backup is created before cleaning.", classes="stat-label")
            with Horizontal(id="button-row"):
                yield Button("Scan Registry", id="btn-reg-scan", variant="primary")
                yield Button("Clean Selected", id="btn-reg-clean", variant="error")
            yield ProgressBar(total=3, show_eta=False, id="reg-progress")
            yield Label("", id="reg-status", classes="stat-label")
            yield DataTable(id="reg-table", zebra_stripes=True)
            yield RichLog(id="reg-log", highlight=True, markup=True)

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#reg-table")
        tbl.add_columns("✓", "Type", "Key", "Description")
        self._issues: list = []
        self._selected: set[int] = set()

    @on(Button.Pressed, "#btn-reg-scan")
    def do_scan(self) -> None:
        self._run_reg_scan()

    @on(Button.Pressed, "#btn-reg-clean")
    def do_clean(self) -> None:
        if not self._issues:
            return
        self.app.push_screen(
            ConfirmModal("Clean selected registry issues? A backup will be saved first.", "Confirm"),
            self._on_confirm,
        )

    def _on_confirm(self, confirmed: bool) -> None:
        if confirmed:
            self._run_reg_clean()

    @on(DataTable.RowSelected)
    def row_clicked(self, event: DataTable.RowSelected) -> None:
        idx = event.cursor_row
        if idx in self._selected:
            self._selected.discard(idx)
        else:
            self._selected.add(idx)
        self._refresh_table()

    def _refresh_table(self) -> None:
        tbl: DataTable = self.query_one("#reg-table")
        tbl.clear()
        for i, issue in enumerate(self._issues):
            check = "☑" if i in self._selected else "☐"
            tbl.add_row(check, issue.issue_type, issue.full_path[:40], issue.description[:50], key=str(i))

    @work(thread=True)
    def _run_reg_scan(self) -> None:
        from pcleaner.core.registry import RegistryScanner
        log_w: RichLog = self.query_one("#reg-log")
        bar: ProgressBar = self.query_one("#reg-progress")

        def cb(label, cur, _tot):
            self.app.call_from_thread(bar.update, progress=cur)
            self.app.call_from_thread(log_w.write, f"[dim]Checking {label}...[/dim]")

        self.app.call_from_thread(self.query_one("#reg-status", Label).update, "Scanning registry...")
        issues = RegistryScanner().scan(progress_cb=cb)
        self._issues = issues
        self._selected = set(range(len(issues)))
        self.app.call_from_thread(self._refresh_table)
        self.app.call_from_thread(
            self.query_one("#reg-status", Label).update,
            f"Found {len(issues)} issues"
        )
        self.app.call_from_thread(
            log_w.write, f"[green]Scan complete: {len(issues)} issues found[/green]"
        )

    @work(thread=True)
    def _run_reg_clean(self) -> None:
        from pcleaner.core.registry import RegistryCleaner
        log_w: RichLog = self.query_one("#reg-log")
        selected = [self._issues[i] for i in sorted(self._selected)]
        self.app.call_from_thread(log_w.write, "[dim]Creating registry backup...[/dim]")
        cleaner = RegistryCleaner()
        backup = cleaner.backup_full()
        if backup:
            self.app.call_from_thread(log_w.write, f"[dim]Backup: {backup}[/dim]")
        cleaned, errors = cleaner.clean(selected)
        self.app.call_from_thread(
            log_w.write, f"[green]✓ Cleaned {cleaned} entries. {errors} errors.[/green]"
        )
        self._issues = []
        self._selected.clear()
        self.app.call_from_thread(self._refresh_table)


# ---------------------------------------------------------------------------
# Startup tab
# ---------------------------------------------------------------------------

class StartupPane(TabPane):
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Startup Manager", classes="panel-title")
            yield Label("Control programs that run when Windows starts.", classes="stat-label")
            with Horizontal(id="button-row"):
                yield Button("Refresh",  id="btn-startup-refresh", variant="primary")
                yield Button("Disable",  id="btn-startup-disable", variant="warning")
                yield Button("Enable",   id="btn-startup-enable")
                yield Button("Delete",   id="btn-startup-delete",  variant="error")
            yield DataTable(id="startup-table", zebra_stripes=True)
            yield RichLog(id="startup-log", markup=True)

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#startup-table")
        tbl.add_columns("#", "Name", "Source", "Status", "Command")
        self._entries: list = []
        self._load_entries()

    @on(Button.Pressed, "#btn-startup-refresh")
    def do_refresh(self) -> None:
        self._load_entries()

    @on(Button.Pressed, "#btn-startup-disable")
    def do_disable(self) -> None:
        self._act("disable")

    @on(Button.Pressed, "#btn-startup-enable")
    def do_enable(self) -> None:
        self._act("enable")

    @on(Button.Pressed, "#btn-startup-delete")
    def do_delete(self) -> None:
        self.app.push_screen(
            ConfirmModal("Permanently delete this startup entry?"),
            lambda ok: self._act("delete") if ok else None,
        )

    def _act(self, action: str) -> None:
        tbl: DataTable = self.query_one("#startup-table")
        row = tbl.cursor_row
        if row >= len(self._entries):
            return
        entry = self._entries[row]
        from pcleaner.tools.startup import StartupManager
        mgr = StartupManager()
        log_w: RichLog = self.query_one("#startup-log")
        if action == "disable":
            ok = mgr.disable(entry)
            log_w.write(f"{'[green]Disabled' if ok else '[red]Failed to disable'} {entry.name}[/]")
        elif action == "enable":
            ok = mgr.enable(entry)
            log_w.write(f"{'[green]Enabled' if ok else '[red]Failed to enable'} {entry.name}[/]")
        elif action == "delete":
            ok = mgr.delete(entry)
            log_w.write(f"{'[green]Deleted' if ok else '[red]Failed to delete'} {entry.name}[/]")
        if ok:
            self._load_entries()

    @work(thread=True)
    def _load_entries(self) -> None:
        from pcleaner.tools.startup import StartupManager
        entries = StartupManager().list_entries()
        self._entries = entries
        tbl: DataTable = self.query_one("#startup-table")
        self.app.call_from_thread(tbl.clear)
        for i, e in enumerate(entries):
            status = "[green]Enabled[/]" if e.enabled else "[red]Disabled[/]"
            self.app.call_from_thread(
                tbl.add_row, str(i + 1), e.name[:28], e.source, status, e.command[:40]
            )


# ---------------------------------------------------------------------------
# Uninstaller tab
# ---------------------------------------------------------------------------

class UninstallerPane(TabPane):
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Software Uninstaller", classes="panel-title")
            yield Input(placeholder="Search programs...", id="uninstall-search")
            with Horizontal(id="button-row"):
                yield Button("Refresh",   id="btn-uninst-refresh", variant="primary")
                yield Button("Uninstall", id="btn-uninst-uninstall", variant="error")
            yield DataTable(id="uninst-table", zebra_stripes=True)
            yield RichLog(id="uninst-log", markup=True)

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#uninst-table")
        tbl.add_columns("Name", "Version", "Publisher", "Size", "Date")
        self._programs: list = []
        self._filtered: list = []
        self._load_programs()

    @on(Button.Pressed, "#btn-uninst-refresh")
    def do_refresh(self) -> None:
        self._load_programs()

    @on(Button.Pressed, "#btn-uninst-uninstall")
    def do_uninstall(self) -> None:
        tbl: DataTable = self.query_one("#uninst-table")
        row = tbl.cursor_row
        if row >= len(self._filtered):
            return
        prog = self._filtered[row]
        self.app.push_screen(
            ConfirmModal(f"Uninstall '{prog.name}'?", "Confirm Uninstall"),
            lambda ok: self._run_uninstall(prog) if ok else None,
        )

    @on(Input.Changed, "#uninstall-search")
    def on_search(self, event: Input.Changed) -> None:
        q = event.value.lower()
        self._filtered = [p for p in self._programs if q in p.name.lower() or q in p.publisher.lower()] if q else self._programs
        self._refresh_table()

    def _refresh_table(self) -> None:
        tbl: DataTable = self.query_one("#uninst-table")
        tbl.clear()
        for p in self._filtered:
            tbl.add_row(p.name[:35], p.version[:15], p.publisher[:25], p.size_str, p.install_date)

    def _run_uninstall(self, prog) -> None:
        from pcleaner.tools.uninstaller import Uninstaller
        ok = Uninstaller().uninstall(prog)
        log_w: RichLog = self.query_one("#uninst-log")
        log_w.write(
            f"{'[green]Launching uninstaller for' if ok else '[red]Failed to launch:'} {prog.name}[/]"
        )

    @work(thread=True)
    def _load_programs(self) -> None:
        from pcleaner.tools.uninstaller import Uninstaller
        programs = Uninstaller().list_programs()
        self._programs = programs
        self._filtered = programs
        self.app.call_from_thread(self._refresh_table)
        self.app.call_from_thread(
            self.query_one("#uninst-log", RichLog).write,
            f"[dim]Loaded {len(programs)} installed programs.[/dim]"
        )


# ---------------------------------------------------------------------------
# Disk Analyzer tab
# ---------------------------------------------------------------------------

class DiskPane(TabPane):
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Disk Analyzer", classes="panel-title")
            with Horizontal(id="button-row"):
                yield Input(placeholder="Path to analyze (default: C:\\Users)", id="disk-path")
                yield Button("Analyze", id="btn-disk-analyze", variant="primary")
            yield ProgressBar(total=100, show_eta=False, id="disk-progress")
            yield Label("", id="disk-status", classes="stat-label")
            yield DataTable(id="disk-table", zebra_stripes=True)
            yield RichLog(id="disk-log", markup=True)

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#disk-table")
        tbl.add_columns("Category", "Files", "Size", "Share")

    @on(Button.Pressed, "#btn-disk-analyze")
    def do_analyze(self) -> None:
        path_str = self.query_one("#disk-path", Input).value.strip() or str(Path.home())
        self._run_analysis(Path(path_str))

    @work(thread=True)
    def _run_analysis(self, path: Path) -> None:
        from pcleaner.tools.disk_analyzer import DiskAnalyzer
        log_w: RichLog = self.query_one("#disk-log")
        bar: ProgressBar = self.query_one("#disk-progress")

        self.app.call_from_thread(self.query_one("#disk-status", Label).update, f"Analyzing {path}...")

        def cb(_cur_path: str, count: int) -> None:
            self.app.call_from_thread(bar.update, progress=min(count // 100, 100))
            self.app.call_from_thread(self.query_one("#disk-status", Label).update, f"Scanned {count} files...")

        analyzer = DiskAnalyzer()
        analyzer.set_progress_callback(cb)
        result = analyzer.analyze(path)

        tbl: DataTable = self.query_one("#disk-table")
        self.app.call_from_thread(tbl.clear)
        for cat in result.sorted_categories():
            if cat.size == 0:
                continue
            pct = result.percent(cat.name)
            bar_filled = int(pct / 100 * 20)
            bar_str = "█" * bar_filled + "░" * (20 - bar_filled) + f" {pct:.1f}%"
            self.app.call_from_thread(
                tbl.add_row, cat.name, str(cat.count), cat.size_str, bar_str
            )

        self.app.call_from_thread(bar.update, progress=100)
        self.app.call_from_thread(
            self.query_one("#disk-status", Label).update,
            f"Total: {result.total_size_str} in {result.total_files} files"
        )
        self.app.call_from_thread(
            log_w.write,
            f"[green]Analysis complete: {result.total_size_str} in {result.total_files} files[/green]"
        )


# ---------------------------------------------------------------------------
# Duplicates tab
# ---------------------------------------------------------------------------

class DuplicatesPane(TabPane):
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Duplicate File Finder", classes="panel-title")
            with Horizontal(id="button-row"):
                yield Input(placeholder="Directory to scan...", id="dup-path")
                yield Button("Scan",   id="btn-dup-scan",   variant="primary")
                yield Button("Delete", id="btn-dup-delete", variant="error")
            yield ProgressBar(total=100, show_eta=False, id="dup-progress")
            yield Label("", id="dup-status", classes="stat-label")
            yield DataTable(id="dup-table", zebra_stripes=True)
            yield RichLog(id="dup-log", markup=True)

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#dup-table")
        tbl.add_columns("#", "Files", "Size Each", "Wasted", "Example")
        self._groups: list = []

    @on(Button.Pressed, "#btn-dup-scan")
    def do_scan(self) -> None:
        path_str = self.query_one("#dup-path", Input).value.strip() or str(Path.home())
        self._run_scan(Path(path_str))

    @on(Button.Pressed, "#btn-dup-delete")
    def do_delete(self) -> None:
        if not self._groups:
            return
        self.app.push_screen(
            ConfirmModal("Delete all duplicate files? (Keeps the newest copy of each)", "Confirm"),
            lambda ok: self._run_delete() if ok else None,
        )

    @work(thread=True)
    def _run_scan(self, path: Path) -> None:
        from pcleaner.tools.duplicates import DuplicateFinder
        log_w: RichLog = self.query_one("#dup-log")
        bar: ProgressBar = self.query_one("#dup-progress")

        def cb(phase, cur, _tot):
            self.app.call_from_thread(
                self.query_one("#dup-status", Label).update, f"{phase}: {cur}..."
            )

        finder = DuplicateFinder()
        finder.set_progress_callback(cb)
        result = finder.scan([path])
        self._groups = result.groups

        tbl: DataTable = self.query_one("#dup-table")
        self.app.call_from_thread(tbl.clear)
        for i, g in enumerate(result.sorted_by_wasted(), 1):
            self.app.call_from_thread(
                tbl.add_row, str(i), str(len(g.files)), g.size_str, g.wasted_str, str(g.files[0])[:45]
            )

        self.app.call_from_thread(bar.update, progress=100)
        self.app.call_from_thread(
            self.query_one("#dup-status", Label).update,
            f"{len(result.groups)} duplicate groups — {result.total_wasted_str} wasted"
        )
        self.app.call_from_thread(
            log_w.write,
            f"[green]Found {len(result.groups)} groups, {result.total_wasted_str} wasted[/green]"
        )

    @work(thread=True)
    def _run_delete(self) -> None:
        from pcleaner.tools.duplicates import DuplicateFinder
        log_w: RichLog = self.query_one("#dup-log")
        deleted, errors = DuplicateFinder().delete_duplicates(self._groups, keep="newest")
        self.app.call_from_thread(
            log_w.write,
            f"[green]Deleted {deleted} files. {errors} errors.[/green]"
        )
        self._groups = []
        tbl: DataTable = self.query_one("#dup-table")
        self.app.call_from_thread(tbl.clear)


# ---------------------------------------------------------------------------
# Health tab
# ---------------------------------------------------------------------------

class HealthPane(TabPane):
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("System Health", classes="panel-title")
            with Horizontal(id="button-row"):
                yield Button("Refresh", id="btn-health-refresh", variant="primary")
            yield DataTable(id="health-table", zebra_stripes=True)
            yield Label("", id="health-recs", classes="warning-text")

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#health-table")
        tbl.add_columns("Metric", "Value", "Status")
        self._load_health()

    @on(Button.Pressed, "#btn-health-refresh")
    def do_refresh(self) -> None:
        self._load_health()

    @work(thread=True)
    def _load_health(self) -> None:
        from pcleaner.tools.health import HealthChecker
        report = HealthChecker().check()
        tbl: DataTable = self.query_one("#health-table")
        self.app.call_from_thread(tbl.clear)

        def status_icon(pct: float) -> str:
            if pct > 90: return "[red]Critical[/]"
            if pct > 75: return "[yellow]Warning[/]"
            return "[green]Good[/]"

        rows = [
            ("OS",          report.os_name,       "[green]OK[/]"),
            ("CPU",         report.cpu_brand[:40], "[green]OK[/]"),
            ("CPU Cores",   f"{report.cpu_cores}C / {report.cpu_threads}T", "[green]OK[/]"),
            ("CPU Usage",   f"{report.cpu_usage:.1f}%", status_icon(report.cpu_usage)),
            ("RAM",         f"{report.ram_used_str} / {report.ram_total_str}", status_icon(report.ram_percent)),
            ("Uptime",      report.uptime_str,     "[green]OK[/]"),
            ("Processes",   str(report.total_processes), "[green]OK[/]"),
            ("Startup Items", str(report.startup_count),
             "[yellow]High[/]" if report.startup_count > 15 else "[green]OK[/]"),
        ]
        for drive in report.drives:
            rows.append((
                f"Drive {drive.drive}",
                f"{drive.used_str} / {drive.total_str} ({drive.percent_used:.0f}%)",
                status_icon(drive.percent_used),
            ))

        for row in rows:
            self.app.call_from_thread(tbl.add_row, *row)

        recs = "\n".join(f"• {r}" for r in report.recommendations)
        self.app.call_from_thread(self.query_one("#health-recs", Label).update, recs)


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

def _fmt(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n //= 1024
    return f"{n:.1f} TB"


class PCleanerTUI(App):
    """PCleaner Terminal UI."""

    CSS_PATH = _CSS_PATH
    TITLE = APP_FULL_NAME
    SUB_TITLE = f"v{__version__}"

    BINDINGS = [
        Binding("q",      "quit",          "Quit",    show=True),
        Binding("ctrl+c", "quit",          "Quit",    show=False),
        Binding("f1",     "show_cleaner",  "Cleaner", show=True),
        Binding("f2",     "show_registry", "Registry",show=True),
        Binding("f3",     "show_tools",    "Tools",   show=True),
        Binding("f5",     "show_health",   "Health",  show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(id="main-tabs"):
            yield CleanerPane(    "Cleaner",    id="tab-cleaner")
            yield RegistryPane(   "Registry",   id="tab-registry")
            yield StartupPane(    "Startup",    id="tab-startup")
            yield UninstallerPane("Uninstaller",id="tab-uninst")
            yield DiskPane(       "Disk",       id="tab-disk")
            yield DuplicatesPane( "Duplicates", id="tab-dup")
            yield HealthPane(     "Health",     id="tab-health")
        yield Footer()

    def action_show_cleaner(self)  -> None: self.query_one("#main-tabs", TabbedContent).active = "tab-cleaner"
    def action_show_registry(self) -> None: self.query_one("#main-tabs", TabbedContent).active = "tab-registry"
    def action_show_tools(self)    -> None: self.query_one("#main-tabs", TabbedContent).active = "tab-startup"
    def action_show_health(self)   -> None: self.query_one("#main-tabs", TabbedContent).active = "tab-health"
