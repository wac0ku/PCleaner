"""Duplicate file finder screen."""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import Button, DataTable, Input, Label, ProgressBar, RichLog, Static


class DuplicatesScreen(Container):
    """Find and remove duplicate files."""

    def __init__(self) -> None:
        super().__init__(id="screen-duplicates")
        self._groups: list = []

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold cyan]━━━  Duplicate Finder  ━━━[/]",
            classes="screen-title",
        )
        yield Static(
            "  [dim]Hash-based (MD5) duplicate detection — keeps the newest copy.[/]",
            classes="screen-subtitle",
        )

        with Horizontal(classes="action-bar"):
            yield Input(
                placeholder="📁  Directory to scan…",
                id="dup-path",
            )
            yield Button("🔍  Scan", id="btn-dup-scan", variant="primary")
            yield Button("🗑  Delete Dupes", id="btn-dup-delete", variant="error")

        yield ProgressBar(total=100, show_eta=False, id="dup-progress")

        with Horizontal(classes="status-row"):
            yield Label("", id="dup-status", classes="status-label")
            yield Label("", id="dup-wasted", classes="size-badge")

        yield DataTable(id="dup-table", zebra_stripes=True)

        with ScrollableContainer(classes="log-container"):
            yield RichLog(id="dup-log", markup=True)

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#dup-table")
        tbl.add_columns("#", "Copies", "Size Each", "Wasted", "Example Path")

    @on(Button.Pressed, "#btn-dup-scan")
    def do_scan(self) -> None:
        path_str = self.query_one("#dup-path", Input).value.strip()
        path = Path(path_str) if path_str else Path.home()
        self._run_scan(path)

    @on(Button.Pressed, "#btn-dup-delete")
    def do_delete(self) -> None:
        if not self._groups:
            return
        from pcleaner.tui.app import ConfirmModal
        self.app.push_screen(
            ConfirmModal(
                "Delete all duplicate files?\n(Keeps the newest copy of each group)",
                "Confirm Delete",
            ),
            lambda ok: self._run_delete() if ok else None,
        )

    @work(thread=True)
    def _run_scan(self, path: Path) -> None:
        from pcleaner.tools.duplicates import DuplicateFinder

        log_w: RichLog = self.query_one("#dup-log")
        bar: ProgressBar = self.query_one("#dup-progress")

        def cb(phase, cur, _tot):
            self.app.call_from_thread(
                self.query_one("#dup-status", Label).update,
                f"⏳ {phase}: {cur}…"
            )

        self.app.call_from_thread(
            self.query_one("#dup-status", Label).update, "⏳ Scanning for duplicates…"
        )
        finder = DuplicateFinder()
        finder.set_progress_callback(cb)
        result = finder.scan([path])
        self._groups = result.groups

        tbl: DataTable = self.query_one("#dup-table")
        self.app.call_from_thread(tbl.clear)
        for i, g in enumerate(result.sorted_by_wasted(), 1):
            self.app.call_from_thread(
                tbl.add_row,
                str(i),
                str(len(g.files)),
                g.size_str,
                g.wasted_str,
                str(g.files[0])[:50],
            )

        self.app.call_from_thread(bar.update, progress=100)
        self.app.call_from_thread(
            self.query_one("#dup-status", Label).update,
            f"[green]✓[/] {len(result.groups)} duplicate groups found",
        )
        self.app.call_from_thread(
            self.query_one("#dup-wasted", Label).update,
            f"  ⚠ {result.total_wasted_str} wasted",
        )
        self.app.call_from_thread(
            log_w.write,
            f"[green]✓ Found {len(result.groups)} groups, "
            f"{result.total_wasted_str} wasted[/green]",
        )

    @work(thread=True)
    def _run_delete(self) -> None:
        from pcleaner.tools.duplicates import DuplicateFinder

        log_w: RichLog = self.query_one("#dup-log")
        deleted, errors = DuplicateFinder().delete_duplicates(
            self._groups, keep="newest"
        )
        self.app.call_from_thread(
            log_w.write,
            f"[green]✓ Deleted {deleted} files. {errors} errors.[/green]",
        )
        self._groups = []
        tbl: DataTable = self.query_one("#dup-table")
        self.app.call_from_thread(tbl.clear)
        self.app.call_from_thread(
            self.query_one("#dup-wasted", Label).update, ""
        )
