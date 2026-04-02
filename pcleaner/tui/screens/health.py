"""Detailed system health screen."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Button, DataTable, Label, ProgressBar, Static


class HealthScreen(Container):
    """Detailed system health report with process list."""

    def __init__(self) -> None:
        super().__init__(id="screen-health")

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold cyan]━━━  System Health  ━━━[/]",
            classes="screen-title",
        )
        yield Static(
            "  [dim]Comprehensive system health report with metrics and recommendations.[/]",
            classes="screen-subtitle",
        )

        with Horizontal(classes="action-bar"):
            yield Button("⟳  Refresh", id="btn-health-refresh", variant="primary")
            yield Button("📋  DNS Flush", id="btn-health-dns")
            yield Button("📎  Clear Clipboard", id="btn-health-clipboard")

        yield ProgressBar(total=100, show_eta=False, id="health-progress")

        yield Static("", id="health-system-info", classes="health-card")
        yield Static("", id="health-drives", classes="health-card")

        yield DataTable(id="health-process-table", zebra_stripes=True)

        yield Static("", id="health-recs", classes="recs-panel")

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#health-process-table")
        tbl.add_columns("PID", "Name", "CPU %", "RAM (MB)", "Status")
        self._load_health()

    @on(Button.Pressed, "#btn-health-refresh")
    def do_refresh(self) -> None:
        self._load_health()

    @on(Button.Pressed, "#btn-health-dns")
    def do_dns_flush(self) -> None:
        self._flush_dns()

    @on(Button.Pressed, "#btn-health-clipboard")
    def do_clear_clipboard(self) -> None:
        self._clear_clipboard()

    @work(thread=True)
    def _load_health(self) -> None:
        from pcleaner.tools.health import HealthChecker
        bar: ProgressBar = self.query_one("#health-progress")
        self.app.call_from_thread(bar.update, progress=0)
        report = HealthChecker().check()
        self.app.call_from_thread(bar.update, progress=30)

        # System info card
        def _status_color(pct: float) -> str:
            if pct > 90:
                return "red"
            if pct > 70:
                return "yellow"
            return "green"

        cpu_color = _status_color(report.cpu_usage)
        ram_color = _status_color(report.ram_percent)

        sys_lines = [
            "  [bold cyan]🖥  System Information[/]\n",
            f"    OS          [white]{report.os_name}[/]",
            f"    CPU         [white]{report.cpu_brand[:50]}[/]",
            f"    Cores       [white]{report.cpu_cores}C / {report.cpu_threads}T[/]",
            f"    CPU Usage   [{cpu_color}]{report.cpu_usage:.1f}%[/]",
            f"    RAM         [{ram_color}]{report.ram_used_str} / {report.ram_total_str}"
            f"  ({report.ram_percent:.1f}%)[/]",
            f"    Uptime      [white]{report.uptime_str}[/]",
            f"    Processes   [white]{report.total_processes}[/]",
            f"    Startup     [white]{report.startup_count} programs[/]",
        ]
        self.app.call_from_thread(
            self.query_one("#health-system-info", Static).update,
            "\n".join(sys_lines),
        )
        self.app.call_from_thread(bar.update, progress=55)

        # Drive cards
        drive_lines = ["  [bold cyan]💽  Disk Drives[/]\n"]
        for d in report.drives:
            pct = d.percent_used
            color = _status_color(pct)
            bar_w = 20
            filled = int(pct / 100 * bar_w)
            empty = bar_w - filled
            bar = f"[{color}]{'━' * filled}[/][dim]{'╌' * empty}[/]"
            drive_lines.append(
                f"    {d.drive:<6} {bar}  [{color}]{pct:5.1f}%[/]  "
                f"[dim]{d.used_str} / {d.total_str}  ({d.free_str} free)[/]"
            )
        self.app.call_from_thread(
            self.query_one("#health-drives", Static).update,
            "\n".join(drive_lines),
        )

        self.app.call_from_thread(bar.update, progress=75)

        # Process table
        tbl: DataTable = self.query_one("#health-process-table")
        self.app.call_from_thread(tbl.clear)
        for p in report.top_processes[:12]:
            self.app.call_from_thread(
                tbl.add_row,
                str(p.pid),
                p.name[:25],
                f"{p.cpu_percent:.1f}",
                f"{p.memory_mb:.1f}",
                p.status,
            )

        self.app.call_from_thread(bar.update, progress=90)

        # Recommendations
        if report.recommendations:
            recs_text = "  [bold yellow]💡 Recommendations[/]\n\n" + "\n".join(
                f"    • {r}" for r in report.recommendations
            )
        else:
            recs_text = "  [green]✓ System looks healthy![/]"
        self.app.call_from_thread(
            self.query_one("#health-recs", Static).update, recs_text
        )
        self.app.call_from_thread(bar.update, progress=100)

    @work(thread=True)
    def _flush_dns(self) -> None:
        from pcleaner.utils.security import run_safe
        try:
            run_safe(["ipconfig", "/flushdns"], timeout=10)
            self.app.call_from_thread(self.app.notify, "DNS cache flushed ✓", severity="information")
        except Exception as e:
            self.app.call_from_thread(self.app.notify, f"DNS flush failed: {e}", severity="error")

    @work(thread=True)
    def _clear_clipboard(self) -> None:
        from pcleaner.utils.security import run_powershell
        try:
            run_powershell("Set-Clipboard -Value $null", timeout=5)
            self.app.call_from_thread(self.app.notify, "Clipboard cleared ✓", severity="information")
        except Exception as e:
            self.app.call_from_thread(self.app.notify, f"Clipboard clear failed: {e}", severity="error")
