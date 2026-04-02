"""Task Manager TUI screen — monitor, detect, and kill suspicious processes."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import Button, DataTable, Label, ProgressBar, RichLog, Static


class TaskManagerScreen(Container):
    """Automated task manager with suspicious process detection."""

    def __init__(self) -> None:
        super().__init__(id="screen-taskmanager")
        self._processes: list = []
        self._suspicious: list = []
        self._show_all = False

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold cyan]━━━  Task Manager  ━━━[/]",
            classes="screen-title",
        )
        yield Static(
            "  [dim]Monitors running processes and detects suspicious activity.[/]",
            classes="screen-subtitle",
        )

        with Horizontal(classes="action-bar"):
            yield Button("🔍  Scan", id="btn-tm-scan", variant="primary")
            yield Button("⛔  Kill Selected", id="btn-tm-kill", variant="error")
            yield Button("⏸  Suspend", id="btn-tm-suspend", variant="warning")
            yield Button("▶  Resume", id="btn-tm-resume")
            yield Button("💀  Kill All Suspicious", id="btn-tm-kill-all", variant="error")

        with Horizontal(classes="action-bar"):
            yield Button(
                "👁  Show Suspicious Only",
                id="btn-tm-toggle-view",
            )
            yield Button("⟳  Refresh", id="btn-tm-refresh")

        yield ProgressBar(total=100, show_eta=False, id="tm-progress")

        with Horizontal(classes="status-row"):
            yield Label("", id="tm-status", classes="status-label")
            yield Label("", id="tm-counts", classes="count-badge")

        yield Static("", id="tm-threat-summary", classes="threat-summary")

        yield DataTable(id="tm-table", zebra_stripes=True)

        with ScrollableContainer(classes="log-container"):
            yield RichLog(id="tm-log", highlight=True, markup=True)

    def on_mount(self) -> None:
        tbl: DataTable = self.query_one("#tm-table")
        tbl.add_columns(
            "⚠", "PID", "Name", "CPU %", "RAM (MB)",
            "Score", "Status", "Reason",
        )
        self._run_scan()

    @on(Button.Pressed, "#btn-tm-scan")
    def do_scan(self) -> None:
        self._run_scan()

    @on(Button.Pressed, "#btn-tm-refresh")
    def do_refresh(self) -> None:
        self._run_scan()

    @on(Button.Pressed, "#btn-tm-kill")
    def do_kill(self) -> None:
        tbl: DataTable = self.query_one("#tm-table")
        row = tbl.cursor_row
        display = self._suspicious if not self._show_all else self._processes
        if row >= len(display):
            return
        proc = display[row]
        if proc.is_protected:
            self.query_one("#tm-log", RichLog).write(
                f"[red]⛔ Cannot kill protected system process: {proc.name}[/]"
            )
            return
        from pcleaner.tui.app import ConfirmModal
        self.app.push_screen(
            ConfirmModal(
                f"Kill process '{proc.name}' (PID {proc.pid})?\n"
                f"Severity: {proc.severity_icon} {proc.severity}\n"
                f"Reason: {proc.reason_summary}",
                "Confirm Kill Process",
            ),
            lambda ok: self._kill_pid(proc.pid) if ok else None,
        )

    @on(Button.Pressed, "#btn-tm-suspend")
    def do_suspend(self) -> None:
        tbl: DataTable = self.query_one("#tm-table")
        row = tbl.cursor_row
        display = self._suspicious if not self._show_all else self._processes
        if row >= len(display):
            return
        proc = display[row]
        self._suspend_pid(proc.pid)

    @on(Button.Pressed, "#btn-tm-resume")
    def do_resume(self) -> None:
        tbl: DataTable = self.query_one("#tm-table")
        row = tbl.cursor_row
        display = self._suspicious if not self._show_all else self._processes
        if row >= len(display):
            return
        proc = display[row]
        self._resume_pid(proc.pid)

    @on(Button.Pressed, "#btn-tm-kill-all")
    def do_kill_all(self) -> None:
        if not self._suspicious:
            self.query_one("#tm-log", RichLog).write(
                "[yellow]⚠ No suspicious processes found.[/]"
            )
            return

        high_critical = [
            p for p in self._suspicious
            if p.severity in ("high", "critical") and not p.is_protected
        ]
        if not high_critical:
            self.query_one("#tm-log", RichLog).write(
                "[yellow]⚠ No high/critical severity processes to kill.[/]"
            )
            return

        from pcleaner.tui.app import ConfirmModal
        self.app.push_screen(
            ConfirmModal(
                f"Kill ALL {len(high_critical)} suspicious processes\n"
                f"with HIGH or CRITICAL severity?\n\n"
                f"⚠ This action cannot be undone!",
                "⚠ Kill All Suspicious",
            ),
            lambda ok: self._kill_all_suspicious() if ok else None,
        )

    @on(Button.Pressed, "#btn-tm-toggle-view")
    def do_toggle_view(self) -> None:
        self._show_all = not self._show_all
        btn = self.query_one("#btn-tm-toggle-view", Button)
        if self._show_all:
            btn.label = "👁  Show Suspicious Only"
        else:
            btn.label = "👁  Show All Processes"
        self._refresh_table()

    def _refresh_table(self) -> None:
        tbl: DataTable = self.query_one("#tm-table")
        tbl.clear()

        display = self._processes if self._show_all else self._suspicious

        for proc in display:
            severity_color = {
                "critical": "red",
                "high": "rgb(255,140,0)",
                "medium": "yellow",
                "low": "cyan",
                "clean": "green",
            }.get(proc.severity, "dim")

            icon = proc.severity_icon
            score_display = (
                f"[{severity_color}]{proc.suspicion_score}[/]"
                if proc.suspicion_score > 0
                else "[green]0[/]"
            )

            protected = " 🛡" if proc.is_protected else ""
            reason = proc.reason_summary[:40] if proc.is_suspicious else ""

            tbl.add_row(
                icon,
                str(proc.pid),
                f"{proc.name[:22]}{protected}",
                f"{proc.cpu_percent:.1f}",
                f"{proc.memory_mb:.1f}",
                score_display,
                proc.status,
                reason,
            )

        # Update counts
        critical = sum(1 for p in self._suspicious if p.severity == "critical")
        high = sum(1 for p in self._suspicious if p.severity == "high")
        medium = sum(1 for p in self._suspicious if p.severity == "medium")
        low = sum(1 for p in self._suspicious if p.severity == "low")

        self.query_one("#tm-counts", Label).update(
            f"  🔴 {critical}  🟠 {high}  🟡 {medium}  🔵 {low}  "
            f"│  {len(self._processes)} total"
        )

        # Threat summary
        if critical > 0 or high > 0:
            summary = (
                f"  [bold red]⚠ THREATS DETECTED[/]  —  "
                f"[red]{critical} critical[/], [rgb(255,140,0)]{high} high[/] "
                f"severity processes found!"
            )
        elif medium > 0:
            summary = (
                f"  [yellow]⚡ Attention[/]  —  "
                f"{medium} medium severity processes detected."
            )
        elif low > 0:
            summary = f"  [cyan]ℹ {low} low-severity items detected. System looks OK.[/]"
        else:
            summary = "  [green]✓ No suspicious processes detected. System is clean![/]"

        self.query_one("#tm-threat-summary", Static).update(summary)

    @work(thread=True)
    def _run_scan(self) -> None:
        from pcleaner.tools.task_manager import TaskManager

        log_w: RichLog = self.query_one("#tm-log")
        bar: ProgressBar = self.query_one("#tm-progress")

        self.app.call_from_thread(
            self.query_one("#tm-status", Label).update,
            "⏳ Scanning processes…"
        )

        def cb(phase, cur, total):
            pct = int(cur / max(total, 1) * 100)
            self.app.call_from_thread(bar.update, progress=pct)

        mgr = TaskManager()
        mgr.set_progress_callback(cb)
        result = mgr.scan()

        self._processes = result.all_processes
        self._suspicious = result.suspicious

        self.app.call_from_thread(bar.update, progress=100)
        self.app.call_from_thread(self._refresh_table)
        self.app.call_from_thread(
            self.query_one("#tm-status", Label).update,
            f"[green]✓[/] Scanned {len(result.all_processes)} processes  "
            f"— {result.suspicious_count} suspicious",
        )

        if result.suspicious_count > 0:
            self.app.call_from_thread(
                log_w.write,
                f"[yellow]⚠ Found {result.suspicious_count} suspicious processes "
                f"({result.critical_count} critical, {result.high_count} high)[/]",
            )
        else:
            self.app.call_from_thread(
                log_w.write,
                "[green]✓ No suspicious processes found. System is clean![/]",
            )

    def _kill_pid(self, pid: int) -> None:
        self._do_kill(pid)

    @work(thread=True)
    def _do_kill(self, pid: int) -> None:
        from pcleaner.tools.task_manager import TaskManager
        log_w: RichLog = self.query_one("#tm-log")
        ok, msg = TaskManager().kill_process(pid)
        if ok:
            self.app.call_from_thread(log_w.write, f"[green]✓ {msg}[/]")
            self.app.call_from_thread(self.app.notify, msg, severity="information")
        else:
            self.app.call_from_thread(log_w.write, f"[red]✗ {msg}[/]")
            self.app.call_from_thread(self.app.notify, msg, severity="error")
        # Refresh
        self._run_scan()

    @work(thread=True)
    def _suspend_pid(self, pid: int) -> None:
        from pcleaner.tools.task_manager import TaskManager
        log_w: RichLog = self.query_one("#tm-log")
        ok, msg = TaskManager().suspend_process(pid)
        if ok:
            self.app.call_from_thread(log_w.write, f"[yellow]⏸ {msg}[/]")
            self.app.call_from_thread(self.app.notify, msg, severity="information")
        else:
            self.app.call_from_thread(log_w.write, f"[red]✗ {msg}[/]")
        self._run_scan()

    @work(thread=True)
    def _resume_pid(self, pid: int) -> None:
        from pcleaner.tools.task_manager import TaskManager
        log_w: RichLog = self.query_one("#tm-log")
        ok, msg = TaskManager().resume_process(pid)
        if ok:
            self.app.call_from_thread(log_w.write, f"[green]▶ {msg}[/]")
        else:
            self.app.call_from_thread(log_w.write, f"[red]✗ {msg}[/]")
        self._run_scan()

    @work(thread=True)
    def _kill_all_suspicious(self) -> None:
        from pcleaner.tools.task_manager import TaskManager
        log_w: RichLog = self.query_one("#tm-log")

        self.app.call_from_thread(
            log_w.write, "[bold red]💀 Killing all suspicious processes…[/]"
        )

        mgr = TaskManager()
        killed, failed, errors = mgr.kill_all_suspicious(
            self._suspicious, min_severity="high"
        )

        self.app.call_from_thread(
            log_w.write,
            f"[green]✓ Killed {killed} processes.[/] "
            f"[red]{failed} failed.[/]"
        )
        for err in errors:
            self.app.call_from_thread(log_w.write, f"[dim red]  {err}[/]")

        self.app.call_from_thread(
            self.app.notify,
            f"Killed {killed} suspicious processes",
            severity="warning",
        )
        self._run_scan()
