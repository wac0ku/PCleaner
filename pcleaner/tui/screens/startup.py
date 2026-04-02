"""Startup manager screen."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import Button, DataTable, Input, Label, RichLog, Static


class StartupScreen(Container):
    """Manage programs that run at Windows startup."""

    def __init__(self) -> None:
        super().__init__(id="screen-startup")
        self._entries: list = []
        self._filtered: list = []

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold cyan]━━━  Startup Manager  ━━━[/]",
            classes="screen-title",
        )
        yield Static(
            "  [dim]Control programs that run when Windows starts.[/]",
            classes="screen-subtitle",
        )

        yield Input(placeholder="🔍  Filter startup programs…", id="startup-search")

        with Horizontal(classes="action-bar"):
            yield Button("⟳  Refresh", id="btn-startup-refresh", variant="primary")
            yield Button("⏸  Disable", id="btn-startup-disable", variant="warning")
            yield Button("▶  Enable", id="btn-startup-enable")
            yield Button("🗑  Delete", id="btn-startup-delete", variant="error")

        with Horizontal(classes="status-row"):
            yield Label("", id="startup-status", classes="status-label")
            yield Label("", id="startup-count", classes="count-badge")

        yield DataTable(id="startup-table", zebra_stripes=True)

        with ScrollableContainer(classes="log-container"):
            yield RichLog(id="startup-log", markup=True)

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#startup-table")
        tbl.add_columns("#", "Name", "Source", "Status", "Command")
        self._load_entries()

    @on(Input.Changed, "#startup-search")
    def on_search(self, event: Input.Changed) -> None:
        q = event.value.lower().strip()
        if q:
            self._filtered = [
                e for e in self._entries
                if q in e.name.lower() or q in e.command.lower()
            ]
        else:
            self._filtered = list(self._entries)
        self._refresh_table()

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
        from pcleaner.tui.app import ConfirmModal
        self.app.push_screen(
            ConfirmModal("Permanently delete this startup entry?"),
            lambda ok: self._act("delete") if ok else None,
        )

    def _act(self, action: str) -> None:
        tbl: DataTable = self.query_one("#startup-table")
        row = tbl.cursor_row
        if row >= len(self._filtered):
            return
        entry = self._filtered[row]
        from pcleaner.tools.startup import StartupManager
        mgr = StartupManager()
        log_w: RichLog = self.query_one("#startup-log")
        ok = False
        if action == "disable":
            ok = mgr.disable(entry)
            msg = f"{'[green]⏸ Disabled' if ok else '[red]✗ Failed to disable'} {entry.name}[/]"
        elif action == "enable":
            ok = mgr.enable(entry)
            msg = f"{'[green]▶ Enabled' if ok else '[red]✗ Failed to enable'} {entry.name}[/]"
        elif action == "delete":
            ok = mgr.delete(entry)
            msg = f"{'[green]🗑 Deleted' if ok else '[red]✗ Failed to delete'} {entry.name}[/]"
        else:
            msg = ""
        log_w.write(msg)
        if ok:
            self._load_entries()

    def _refresh_table(self) -> None:
        tbl: DataTable = self.query_one("#startup-table")
        tbl.clear()
        for i, e in enumerate(self._filtered):
            status = "[green]● Enabled[/]" if e.enabled else "[red]○ Disabled[/]"
            source_badge = f"[cyan]{e.source}[/]"
            tbl.add_row(
                str(i + 1), e.name[:30], source_badge, status, e.command[:45]
            )
        enabled = sum(1 for e in self._filtered if e.enabled)
        total = len(self._filtered)
        self.query_one("#startup-count", Label).update(
            f"  {enabled} enabled / {total} total"
        )

    @work(thread=True)
    def _load_entries(self) -> None:
        from pcleaner.tools.startup import StartupManager
        entries = StartupManager().list_entries()
        self._entries = entries
        self._filtered = list(entries)
        self.app.call_from_thread(self._refresh_table)
        self.app.call_from_thread(
            self.query_one("#startup-status", Label).update,
            f"[green]✓[/] Loaded {len(entries)} startup entries",
        )
