"""Disk analyzer screen."""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import Button, DataTable, Input, Label, ProgressBar, RichLog, Static


class DiskScreen(Container):
    """Analyze disk usage by file type."""

    def __init__(self) -> None:
        super().__init__(id="screen-disk")

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold cyan]━━━  Disk Analyzer  ━━━[/]",
            classes="screen-title",
        )
        yield Static(
            "  [dim]Breakdown of disk usage by file type with top directories.[/]",
            classes="screen-subtitle",
        )

        with Horizontal(classes="action-bar"):
            yield Input(
                placeholder="📁  Path to analyze (default: user home)…",
                id="disk-path",
            )
            yield Button("📊  Analyze", id="btn-disk-analyze", variant="primary")

        yield ProgressBar(total=100, show_eta=False, id="disk-progress")

        with Horizontal(classes="status-row"):
            yield Label("", id="disk-status", classes="status-label")
            yield Label("", id="disk-total", classes="size-badge")

        yield DataTable(id="disk-table", zebra_stripes=True)

        yield Static("", id="disk-top-dirs", classes="top-dirs-panel")

        with ScrollableContainer(classes="log-container"):
            yield RichLog(id="disk-log", markup=True)

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#disk-table")
        tbl.add_columns("Category", "Files", "Size", "Share")

    @on(Button.Pressed, "#btn-disk-analyze")
    def do_analyze(self) -> None:
        path_str = self.query_one("#disk-path", Input).value.strip()
        path = Path(path_str) if path_str else Path.home()
        self._run_analysis(path)

    @work(thread=True)
    def _run_analysis(self, path: Path) -> None:
        from pcleaner.tools.disk_analyzer import DiskAnalyzer

        log_w: RichLog = self.query_one("#disk-log")
        bar: ProgressBar = self.query_one("#disk-progress")

        self.app.call_from_thread(
            self.query_one("#disk-status", Label).update,
            f"⏳ Analyzing {path}…"
        )

        def cb(_cur_path: str, count: int) -> None:
            self.app.call_from_thread(
                bar.update, progress=min(count // 100, 100)
            )
            self.app.call_from_thread(
                self.query_one("#disk-status", Label).update,
                f"⏳ Scanned {count} files…"
            )

        analyzer = DiskAnalyzer()
        analyzer.set_progress_callback(cb)
        result = analyzer.analyze(path)

        tbl: DataTable = self.query_one("#disk-table")
        self.app.call_from_thread(tbl.clear)

        for cat in result.sorted_categories():
            if cat.size == 0:
                continue
            pct = result.percent(cat.name)
            bar_filled = int(pct / 100 * 24)
            bar_empty = 24 - bar_filled

            if pct > 40:
                color = "cyan"
            elif pct > 15:
                color = "blue"
            else:
                color = "dim"

            bar_str = f"[{color}]{'█' * bar_filled}[/][dim]{'░' * bar_empty}[/] {pct:.1f}%"
            self.app.call_from_thread(
                tbl.add_row, cat.name, str(cat.count), cat.size_str, bar_str
            )

        self.app.call_from_thread(bar.update, progress=100)
        self.app.call_from_thread(
            self.query_one("#disk-status", Label).update,
            f"[green]✓[/] {result.total_files} files analyzed",
        )
        self.app.call_from_thread(
            self.query_one("#disk-total", Label).update,
            f"  💽 {result.total_size_str}",
        )

        # Top directories
        if hasattr(result, "largest_dirs") and result.largest_dirs:
            lines = ["  [bold cyan]📁 Top Directories[/]\n"]
            for d in result.largest_dirs[:10]:
                lines.append(f"    [yellow]{d.size_str:>10}[/]  [dim]{str(d.path)[:60]}[/]")
            self.app.call_from_thread(
                self.query_one("#disk-top-dirs", Static).update,
                "\n".join(lines),
            )

        self.app.call_from_thread(
            log_w.write,
            f"[green]✓ Analysis complete: {result.total_size_str} "
            f"in {result.total_files} files[/green]",
        )
