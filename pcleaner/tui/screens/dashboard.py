"""Dashboard home screen — system overview with live gauges."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Button, Label, ProgressBar, Static

from pcleaner.utils.format import fmt_size

from pcleaner import __version__


# ---------------------------------------------------------------------------
# Gauge widget — horizontal bar with label + percentage
# ---------------------------------------------------------------------------

class GaugeBar(Static):
    """A visual gauge bar showing usage percentage."""

    value: reactive[float] = reactive(0.0)

    def __init__(
        self,
        label: str,
        value: float = 0.0,
        suffix: str = "",
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._label = label
        self._suffix = suffix
        self.value = value

    def render(self) -> str:
        pct = max(0.0, min(self.value, 100.0))
        bar_w = 20
        filled = int(pct / 100 * bar_w)
        empty = bar_w - filled

        if pct > 90:
            color = "red"
        elif pct > 70:
            color = "yellow"
        else:
            color = "green"

        bar = f"[{color}]{'━' * filled}[/][dim]{'╌' * empty}[/]"
        return f"  {self._label:<12} {bar}  [{color}]{pct:5.1f}%[/]  {self._suffix}"

    def watch_value(self) -> None:
        self.refresh()


# ---------------------------------------------------------------------------
# Info card — simple bordered card with title + content
# ---------------------------------------------------------------------------

class InfoCard(Static):
    """Small info card with icon + value."""

    def __init__(self, icon: str, title: str, value: str = "—", *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._icon = icon
        self._title = title
        self._value = value
        self.add_class("info-card")

    def render(self) -> str:
        return f"  {self._icon}  [bold]{self._title}[/]\n     [cyan]{self._value}[/]"

    def set_value(self, value: str) -> None:
        self._value = value
        self.refresh()


# ---------------------------------------------------------------------------
# Quick-scan summary card
# ---------------------------------------------------------------------------

class QuickScanCard(Static):
    """Shows estimated reclaimable space per category."""

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._categories: list[tuple[str, str]] = []
        self.add_class("quick-scan-card")

    def render(self) -> str:
        if not self._categories:
            return "  [dim]Press [bold]Scan[/bold] to estimate reclaimable space…[/dim]"

        lines = ["  [bold cyan]⚡ Quick Scan Summary[/]\n"]
        for name, size_str in self._categories:
            lines.append(f"    [white]{name:<22}[/] [yellow]{size_str:>10}[/]")
        return "\n".join(lines)

    def set_categories(self, cats: list[tuple[str, str]]) -> None:
        self._categories = cats
        self.refresh()


# ---------------------------------------------------------------------------
# Dashboard screen
# ---------------------------------------------------------------------------

class DashboardScreen(Container):
    """Home dashboard with system overview and quick scan."""

    DEFAULT_CSS = """
    DashboardScreen {
        height: 1fr;
        padding: 1 2;
    }
    """

    def __init__(self) -> None:
        super().__init__(id="screen-dashboard")
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold cyan]━━━  System Dashboard  ━━━[/]",
            classes="screen-title",
        )

        with Horizontal(classes="gauge-row"):
            with Vertical(classes="gauge-column"):
                yield GaugeBar("CPU", id="gauge-cpu")
                yield GaugeBar("RAM", id="gauge-ram")
            with Vertical(classes="gauge-column"):
                yield GaugeBar("Swap", id="gauge-swap")
                yield Static("", id="uptime-label", classes="info-line")

        with Horizontal(classes="drive-row"):
            yield Static("", id="drive-gauges")

        with Grid(classes="info-grid"):
            yield InfoCard("🖥", "OS", id="info-os")
            yield InfoCard("⚙", "CPU", id="info-cpu")
            yield InfoCard("🕐", "Uptime", id="info-uptime")
            yield InfoCard("📊", "Processes", id="info-procs")
            yield InfoCard("🚀", "Startup", id="info-startup")
            yield InfoCard("💽", "Primary Disk", id="info-disk")

        yield QuickScanCard(id="quick-scan")

        with Horizontal(classes="dash-button-row"):
            yield Button("⟳  Refresh", id="btn-dash-refresh", variant="primary")
            yield Button("⚡ Quick Scan", id="btn-quick-scan", variant="warning")

        yield Static("", id="recs-panel", classes="recs-panel")

    def on_mount(self) -> None:
        self._load_health()

    @on(Button.Pressed, "#btn-dash-refresh")
    def do_refresh(self) -> None:
        self._load_health()

    @on(Button.Pressed, "#btn-quick-scan")
    def do_quick_scan(self) -> None:
        self._run_quick_scan()

    @work(thread=True)
    def _load_health(self) -> None:
        from pcleaner.tools.health import HealthChecker

        report = HealthChecker().check()

        self.app.call_from_thread(
            self.query_one("#gauge-cpu", GaugeBar).__setattr__, "value", report.cpu_usage
        )
        self.app.call_from_thread(
            self.query_one("#gauge-ram", GaugeBar).__setattr__, "value", report.ram_percent
        )

        # Swap
        try:
            import psutil
            swap = psutil.swap_memory()
            swap_pct = swap.percent
        except Exception:
            swap_pct = 0.0
        self.app.call_from_thread(
            self.query_one("#gauge-swap", GaugeBar).__setattr__, "value", swap_pct
        )

        self.app.call_from_thread(
            self.query_one("#uptime-label", Static).update,
            f"  🕐  Uptime: [bold]{report.uptime_str}[/]"
        )

        # Drive gauges
        drive_lines = ["  [bold cyan]Drive Usage[/]\n"]
        for d in report.drives:
            pct = d.percent_used
            bar_w = 16
            filled = int(pct / 100 * bar_w)
            empty = bar_w - filled
            color = "red" if pct > 90 else "yellow" if pct > 75 else "green"
            bar = f"[{color}]{'━' * filled}[/][dim]{'╌' * empty}[/]"
            drive_lines.append(
                f"    {d.drive:<6} {bar}  [{color}]{pct:5.1f}%[/]  "
                f"[dim]{d.used_str} / {d.total_str}[/]"
            )
        self.app.call_from_thread(
            self.query_one("#drive-gauges", Static).update,
            "\n".join(drive_lines)
        )

        # Info cards
        self.app.call_from_thread(self.query_one("#info-os", InfoCard).set_value, report.os_name[:35])
        self.app.call_from_thread(
            self.query_one("#info-cpu", InfoCard).set_value,
            f"{report.cpu_brand[:28]} ({report.cpu_cores}C/{report.cpu_threads}T)"
        )
        self.app.call_from_thread(
            self.query_one("#info-uptime", InfoCard).set_value, report.uptime_str
        )
        self.app.call_from_thread(
            self.query_one("#info-procs", InfoCard).set_value, str(report.total_processes)
        )
        self.app.call_from_thread(
            self.query_one("#info-startup", InfoCard).set_value,
            f"{report.startup_count} programs"
        )
        if report.drives:
            d0 = report.drives[0]
            self.app.call_from_thread(
                self.query_one("#info-disk", InfoCard).set_value,
                f"{d0.free_str} free / {d0.total_str}"
            )

        # Recommendations
        if report.recommendations:
            recs_text = "  [bold yellow]💡 Recommendations[/]\n\n" + "\n".join(
                f"    • {r}" for r in report.recommendations
            )
        else:
            recs_text = "  [green]✓ System looks healthy![/]"
        self.app.call_from_thread(
            self.query_one("#recs-panel", Static).update, recs_text
        )

    @work(thread=True)
    def _run_quick_scan(self) -> None:
        from pcleaner.core.scanner import Scanner

        scanner = Scanner()
        result = scanner.scan_all()

        categories = []
        by_cat = result.by_category()
        for cat_name in sorted(by_cat.keys()):
            items = by_cat[cat_name]
            total = sum(i.size for i in items)
            if total > 0:
                categories.append((cat_name, fmt_size(total)))

        self.app.call_from_thread(
            self.query_one("#quick-scan", QuickScanCard).set_categories, categories
        )


