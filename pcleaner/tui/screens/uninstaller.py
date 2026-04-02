"""Software uninstaller screen."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import Button, DataTable, Input, Label, ProgressBar, RichLog, Static


class UninstallerScreen(Container):
    """Browse installed programs and launch their uninstallers."""

    def __init__(self) -> None:
        super().__init__(id="screen-uninstaller")
        self._programs: list = []
        self._filtered: list = []

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold cyan]━━━  Software Uninstaller  ━━━[/]",
            classes="screen-title",
        )
        yield Static(
            "  [dim]Browse all installed programs and uninstall them.[/]",
            classes="screen-subtitle",
        )

        yield Input(placeholder="🔍  Search programs…", id="uninstall-search")

        with Horizontal(classes="action-bar"):
            yield Button("⟳  Refresh", id="btn-uninst-refresh", variant="primary")
            yield Button("🗑  Uninstall", id="btn-uninst-uninstall", variant="error")

        yield ProgressBar(total=100, show_eta=False, id="uninst-progress")

        with Horizontal(classes="status-row"):
            yield Label("", id="uninst-status", classes="status-label")
            yield Label("", id="uninst-count", classes="count-badge")

        yield DataTable(id="uninst-table", zebra_stripes=True)

        with ScrollableContainer(classes="log-container"):
            yield RichLog(id="uninst-log", markup=True)

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#uninst-table")
        tbl.add_columns("Name", "Version", "Publisher", "Size", "Installed")
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
        from pcleaner.tui.app import ConfirmModal
        self.app.push_screen(
            ConfirmModal(f"Uninstall '{prog.name}'?", "Confirm Uninstall"),
            lambda ok: self._run_uninstall(prog) if ok else None,
        )

    @on(Input.Changed, "#uninstall-search")
    def on_search(self, event: Input.Changed) -> None:
        q = event.value.lower().strip()
        if q:
            self._filtered = [
                p for p in self._programs
                if q in p.name.lower() or q in p.publisher.lower()
            ]
        else:
            self._filtered = list(self._programs)
        self._refresh_table()

    def _refresh_table(self) -> None:
        tbl: DataTable = self.query_one("#uninst-table")
        tbl.clear()
        for p in self._filtered:
            tbl.add_row(
                p.name[:38], p.version[:15], p.publisher[:25],
                p.size_str, p.install_date,
            )
        self.query_one("#uninst-count", Label).update(
            f"  {len(self._filtered)} programs"
        )

    def _run_uninstall(self, prog) -> None:
        from pcleaner.tools.uninstaller import Uninstaller
        ok = Uninstaller().uninstall(prog)
        log_w: RichLog = self.query_one("#uninst-log")
        if ok:
            log_w.write(f"[green]✓ Launching uninstaller for {prog.name}[/]")
        else:
            log_w.write(f"[red]✗ Failed to launch uninstaller for {prog.name}[/]")

    @work(thread=True)
    def _load_programs(self) -> None:
        from pcleaner.tools.uninstaller import Uninstaller

        bar: ProgressBar = self.query_one("#uninst-progress")
        self.app.call_from_thread(bar.update, progress=0)
        self.app.call_from_thread(
            self.query_one("#uninst-status", Label).update, "⏳ Loading programs…"
        )
        programs = Uninstaller().list_programs()
        self._programs = programs
        self._filtered = list(programs)
        self.app.call_from_thread(bar.update, progress=100)
        self.app.call_from_thread(self._refresh_table)
        self.app.call_from_thread(
            self.query_one("#uninst-status", Label).update,
            f"[green]✓[/] Loaded {len(programs)} programs",
        )
