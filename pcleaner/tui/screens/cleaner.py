"""Cleaner screen — scan and clean junk files."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Button, DataTable, Label, ProgressBar, RichLog, Static

from pcleaner.utils.format import fmt_size


class CleanerScreen(Container):
    """Main cleaner: scan + clean junk files."""

    def __init__(self) -> None:
        super().__init__(id="screen-cleaner")
        self._items: list = []
        self._selected: set[int] = set()

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold cyan]━━━  System Cleaner  ━━━[/]",
            classes="screen-title",
        )
        yield Static(
            "  [dim]Select categories to clean and press Analyze, then Clean.[/]",
            classes="screen-subtitle",
        )

        with Horizontal(classes="action-bar"):
            yield Button("🔍  Analyze", id="btn-analyze", variant="primary")
            yield Button("🧹  Clean", id="btn-clean", variant="error")
            yield Button("☑  Select All", id="btn-select-all")
            yield Button("☐  Deselect", id="btn-deselect-all")

        yield ProgressBar(total=100, show_eta=False, id="cleaner-progress")

        with Horizontal(classes="status-row"):
            yield Label("", id="scan-status", classes="status-label")
            yield Label("", id="total-label", classes="size-badge")

        yield DataTable(id="cleaner-table", zebra_stripes=True)

        with ScrollableContainer(classes="log-container"):
            yield RichLog(id="cleaner-log", highlight=True, markup=True)

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#cleaner-table")
        tbl.add_columns("✓", "Category", "Subcategory", "Size", "Admin", "Safe")
        bar: ProgressBar = self.query_one("#cleaner-progress")
        bar.update(progress=0)

    @on(Button.Pressed, "#btn-analyze")
    def do_analyze(self) -> None:
        self._run_scan()

    @on(Button.Pressed, "#btn-clean")
    def do_clean(self) -> None:
        if not self._items:
            self.query_one("#cleaner-log", RichLog).write(
                "[yellow]⚠ Run Analyze first.[/yellow]"
            )
            return
        from pcleaner.tui.app import ConfirmModal
        self.app.push_screen(
            ConfirmModal(
                "This will permanently delete the selected files.\nContinue?",
                "Confirm Clean",
            ),
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
            check = "[green]☑[/]" if i in self._selected else "[dim]☐[/]"
            admin = "[red]⬤[/]" if item.requires_admin else ""
            safe = "[green]✓[/]" if item.safe else "[yellow]⚠[/]"
            tbl.add_row(
                check, item.category, item.subcategory,
                item.size_str, admin, safe, key=str(i),
            )
        total = (
            sum(self._items[i].size for i in self._selected)
            if self._selected
            else sum(it.size for it in self._items)
        )
        self.query_one("#total-label", Label).update(f"  💾 {fmt_size(total)}")

    @work(thread=True)
    def _run_scan(self) -> None:
        from pcleaner.core.scanner import Scanner

        self.app.call_from_thread(self._set_status, "⏳ Scanning…")
        bar: ProgressBar = self.query_one("#cleaner-progress")
        log_widget: RichLog = self.query_one("#cleaner-log")

        def on_progress(label: str, current: int, total: int) -> None:
            pct = int(current / max(total, 1) * 100)
            self.app.call_from_thread(bar.update, progress=pct)
            self.app.call_from_thread(self._set_status, f"⏳ Scanning {label}…")
            self.app.call_from_thread(
                log_widget.write, f"[dim]  Scanning {label}…[/dim]"
            )

        scanner = Scanner()
        scanner.set_progress_callback(on_progress)
        result = scanner.scan_all()
        self._items = result.items
        self._selected = set(range(len(self._items)))

        self.app.call_from_thread(self._refresh_table)
        self.app.call_from_thread(bar.update, progress=100)
        self.app.call_from_thread(
            self._set_status,
            f"[green]✓[/] Found {result.item_count} items — {result.total_size_str}",
        )
        self.app.call_from_thread(
            log_widget.write,
            f"[green]✓ Scan complete: {result.item_count} items, "
            f"{result.total_size_str}[/green]",
        )

    @work(thread=True)
    def _run_clean(self) -> None:
        from pcleaner.core.cleaner import Cleaner
        from pcleaner.core.scanner import ScanResult

        log_widget: RichLog = self.query_one("#cleaner-log")
        bar: ProgressBar = self.query_one("#cleaner-progress")

        selected_items = [self._items[i] for i in sorted(self._selected)]
        if not selected_items:
            self.app.call_from_thread(
                log_widget.write, "[yellow]⚠ No items selected.[/yellow]"
            )
            return

        cleaner = Cleaner()
        scan_result = ScanResult(items=selected_items)

        def on_progress(item, current: int, total: int) -> None:
            pct = int(current / max(total, 1) * 100)
            self.app.call_from_thread(bar.update, progress=pct)
            self.app.call_from_thread(
                log_widget.write,
                f"[dim]  Cleaning {item.subcategory}…[/dim]",
            )

        cleaner.set_progress_callback(on_progress)
        result = cleaner.clean(scan_result)

        self.app.call_from_thread(
            log_widget.write,
            f"[green]✓ Done! Freed {result.freed_str}. "
            f"({len(result.errors)} errors, {len(result.skipped)} skipped)[/green]",
        )
        self.app.call_from_thread(
            self._set_status, f"[green]✓ Cleaned! Freed {result.freed_str}[/]"
        )
        self._items = []
        self._selected.clear()
        self.app.call_from_thread(self._refresh_table)

    def _set_status(self, msg: str) -> None:
        self.query_one("#scan-status", Label).update(msg)
