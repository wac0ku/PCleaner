"""Registry cleaner screen."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Button, DataTable, Label, ProgressBar, RichLog, Static


class RegistryScreen(Container):
    """Registry scanner and cleaner with backup support."""

    def __init__(self) -> None:
        super().__init__(id="screen-registry")
        self._issues: list = []
        self._selected: set[int] = set()

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold cyan]━━━  Registry Cleaner  ━━━[/]",
            classes="screen-title",
        )
        yield Static(
            "  [dim]Scan for orphaned registry entries. A backup is created before cleaning.[/]",
            classes="screen-subtitle",
        )

        with Horizontal(classes="action-bar"):
            yield Button("🔍  Scan Registry", id="btn-reg-scan", variant="primary")
            yield Button("🧹  Clean Selected", id="btn-reg-clean", variant="error")
            yield Button("☑  Select All", id="btn-reg-select-all")
            yield Button("☐  Deselect", id="btn-reg-deselect")

        yield ProgressBar(total=3, show_eta=False, id="reg-progress")

        with Horizontal(classes="status-row"):
            yield Label("", id="reg-status", classes="status-label")
            yield Label("", id="reg-count", classes="count-badge")

        yield DataTable(id="reg-table", zebra_stripes=True)

        with ScrollableContainer(classes="log-container"):
            yield RichLog(id="reg-log", highlight=True, markup=True)

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#reg-table")
        tbl.add_columns("✓", "Type", "Key Path", "Description")

    @on(Button.Pressed, "#btn-reg-scan")
    def do_scan(self) -> None:
        self._run_reg_scan()

    @on(Button.Pressed, "#btn-reg-clean")
    def do_clean(self) -> None:
        if not self._issues:
            return
        from pcleaner.tui.app import ConfirmModal
        self.app.push_screen(
            ConfirmModal(
                "Clean selected registry issues?\nA backup will be saved first.",
                "Confirm Registry Clean",
            ),
            self._on_confirm,
        )

    def _on_confirm(self, confirmed: bool) -> None:
        if confirmed:
            self._run_reg_clean()

    @on(Button.Pressed, "#btn-reg-select-all")
    def select_all(self) -> None:
        self._selected = set(range(len(self._issues)))
        self._refresh_table()

    @on(Button.Pressed, "#btn-reg-deselect")
    def deselect_all(self) -> None:
        self._selected.clear()
        self._refresh_table()

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
            check = "[green]☑[/]" if i in self._selected else "[dim]☐[/]"
            tbl.add_row(
                check,
                issue.issue_type,
                issue.full_path[:50],
                issue.description[:55],
                key=str(i),
            )
        sel_count = len(self._selected)
        total = len(self._issues)
        self.query_one("#reg-count", Label).update(
            f"  {sel_count}/{total} selected" if total > 0 else ""
        )

    @work(thread=True)
    def _run_reg_scan(self) -> None:
        from pcleaner.core.registry import RegistryScanner

        log_w: RichLog = self.query_one("#reg-log")
        bar: ProgressBar = self.query_one("#reg-progress")

        def cb(label, cur, _tot):
            self.app.call_from_thread(bar.update, progress=cur)
            self.app.call_from_thread(
                log_w.write, f"[dim]  Checking {label}…[/dim]"
            )

        self.app.call_from_thread(
            self.query_one("#reg-status", Label).update, "⏳ Scanning registry…"
        )
        issues = RegistryScanner().scan(progress_cb=cb)
        self._issues = issues
        self._selected = set(range(len(issues)))
        self.app.call_from_thread(self._refresh_table)
        self.app.call_from_thread(
            self.query_one("#reg-status", Label).update,
            f"[green]✓[/] Found {len(issues)} issues",
        )
        self.app.call_from_thread(
            log_w.write,
            f"[green]✓ Scan complete: {len(issues)} issues found[/green]",
        )

    @work(thread=True)
    def _run_reg_clean(self) -> None:
        from pcleaner.core.registry import RegistryCleaner

        log_w: RichLog = self.query_one("#reg-log")
        selected = [self._issues[i] for i in sorted(self._selected)]

        self.app.call_from_thread(
            log_w.write, "[dim]  Creating registry backup…[/dim]"
        )
        cleaner = RegistryCleaner()
        backup = cleaner.backup_full()
        if backup:
            self.app.call_from_thread(
                log_w.write, f"[dim]  📁 Backup: {backup}[/dim]"
            )
        cleaned, errors = cleaner.clean(selected)
        self.app.call_from_thread(
            log_w.write,
            f"[green]✓ Cleaned {cleaned} entries. {errors} errors.[/green]",
        )
        self.app.call_from_thread(
            self.query_one("#reg-status", Label).update,
            f"[green]✓ Cleaned {cleaned} entries[/]",
        )
        self._issues = []
        self._selected.clear()
        self.app.call_from_thread(self._refresh_table)
