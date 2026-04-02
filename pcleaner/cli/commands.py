"""Typer CLI commands with Rich output."""

from __future__ import annotations

import sys
import io

# Force UTF-8 output on Windows to support Unicode symbols
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-16"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf-16"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

from pcleaner import BANNER, APP_FULL_NAME, APP_TAGLINE, __version__

console = Console()
err_console = Console(stderr=True)

app = typer.Typer(
    name="pcleaner",
    help=f"{APP_FULL_NAME} — Professional open-source Windows PC cleaner.",
    no_args_is_help=False,
    add_completion=False,
    rich_markup_mode="rich",
)

# Sub-command groups
registry_app = typer.Typer(help="Registry scanner and cleaner.", no_args_is_help=True)
startup_app  = typer.Typer(help="Startup program manager.",      no_args_is_help=True)
disk_app     = typer.Typer(help="Disk usage analyzer.",          no_args_is_help=True)

app.add_typer(registry_app, name="registry")
app.add_typer(startup_app,  name="startup")
app.add_typer(disk_app,     name="disk")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_banner() -> None:
    console.print(f"[bold cyan]{BANNER}[/]")
    console.print(f"[bold white]  {APP_FULL_NAME}[/]  [dim]v{__version__}[/]")
    console.print(f"  [green]{APP_TAGLINE}[/]\n")



# ---------------------------------------------------------------------------
# Main commands
# ---------------------------------------------------------------------------

@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="Show version and exit."),
    gui: bool = typer.Option(False, "--gui", help="Launch the GUI."),
    tui: bool = typer.Option(False, "--tui", help="Launch the TUI."),
) -> None:
    """PCleaner — the free Cleaner App."""
    if version:
        console.print(f"PCleaner v{__version__}")
        raise typer.Exit()

    if gui:
        from pcleaner.__main__ import launch_gui
        launch_gui()
        raise typer.Exit()

    if tui:
        from pcleaner.__main__ import launch_tui
        launch_tui()
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        _print_banner()
        console.print("  Run [bold cyan]pcleaner --help[/] for available commands.\n")
        console.print("  Quick start:")
        console.print("    [cyan]pcleaner clean --dry-run[/]   Preview what will be cleaned")
        console.print("    [cyan]pcleaner clean[/]             Clean junk files")
        console.print("    [cyan]pcleaner health[/]            System health report")
        console.print("    [cyan]pcleaner --tui[/]             Launch TUI interface")
        console.print("    [cyan]pcleaner --gui[/]             Launch GUI interface\n")
        console.print(Panel(
            f"[green]✓ All CCleaner Pro features — completely free[/]\n"
            f"[green]✓ No ads, no nag screens, no telemetry[/]\n"
            f"[green]✓ Open source — MIT license[/]\n"
            f"[dim]  github.com/leongajtner/PCleaner[/]",
            title="[bold cyan]Why PCleaner?[/]",
            border_style="cyan",
            expand=False,
        ))


@app.command()
def clean(
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview only, don't delete anything."),
    categories: Optional[str] = typer.Option(
        None, "--category", "-c",
        help="Comma-separated categories: temp,browser,registry,system,logs,dumps,recycle"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Scan and clean junk files from your system."""
    from pcleaner.core.scanner import Scanner, CATEGORY_LABELS
    from pcleaner.core.cleaner import Cleaner

    _print_banner()

    cat_list = [c.strip() for c in categories.split(",")] if categories else None

    # Scan phase
    scanner = Scanner()
    console.print("[bold]Scanning your system...[/]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning...", total=8)

        def on_progress(label: str, current: int, total: int) -> None:
            progress.update(task, description=f"Scanning {label}...", completed=current, total=total)

        scanner.set_progress_callback(on_progress)
        result = scanner.scan_all(cat_list)

    # Display results table
    if not result.items:
        console.print("[green]✓ Your system is clean! Nothing to remove.[/]")
        return

    table = Table(title="Scan Results", box=box.ROUNDED, border_style="cyan")
    table.add_column("Category",    style="bold white",  no_wrap=True)
    table.add_column("Subcategory", style="dim white")
    table.add_column("Size",        style="yellow", justify="right")
    table.add_column("Admin?",      style="dim",    justify="center")
    table.add_column("Safe?",       style="green",  justify="center")

    by_cat = result.by_category()
    for cat, items in sorted(by_cat.items()):
        for item in items:
            safe_icon  = "[green]✓[/]" if item.safe else "[yellow]⚠[/]"
            admin_icon = "[red]✓[/]"   if item.requires_admin else ""
            table.add_row(cat, item.subcategory, item.size_str, admin_icon, safe_icon)

    console.print(table)
    console.print(f"\n  [bold]Total:[/] [yellow]{result.total_size_str}[/] across [cyan]{result.item_count}[/] items\n")

    if dry_run:
        console.print("[bold yellow]Dry run — no files deleted.[/]")
        return

    if not yes:
        if not Confirm.ask("  Proceed with cleaning?", default=False):
            console.print("[dim]Cancelled.[/]")
            return

    # Clean phase
    cleaner = Cleaner(dry_run=dry_run)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Cleaning...", total=result.item_count)

        def on_clean(item, current: int, total: int) -> None:
            progress.update(task, description=f"Cleaning {item.subcategory}...", completed=current, total=total)

        cleaner.set_progress_callback(on_clean)
        clean_result = cleaner.clean(result)

    console.print(f"\n[bold green]✓ Done![/] Freed [bold yellow]{clean_result.freed_str}[/]")
    if clean_result.skipped:
        console.print(f"  [dim]{len(clean_result.skipped)} items skipped (require admin)[/]")
    if clean_result.errors:
        console.print(f"  [yellow]{len(clean_result.errors)} items could not be deleted[/]")


@app.command()
def health() -> None:
    """Display a system health report."""
    from pcleaner.tools.health import HealthChecker

    _print_banner()
    console.print("[bold]Gathering system information...[/]\n")

    checker = HealthChecker()
    with console.status("Checking system..."):
        report = checker.check()

    # System info
    sys_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    sys_table.add_column("Key",   style="dim white",  no_wrap=True)
    sys_table.add_column("Value", style="bold white")
    sys_table.add_row("OS",        report.os_name)
    sys_table.add_row("CPU",       f"{report.cpu_brand} ({report.cpu_cores}C/{report.cpu_threads}T)")
    sys_table.add_row("CPU Usage", f"{report.cpu_usage:.1f}%")
    sys_table.add_row("RAM",
        f"{report.ram_used_str} / {report.ram_total_str} ({report.ram_percent:.1f}%)")
    sys_table.add_row("Uptime",    report.uptime_str)
    sys_table.add_row("Processes", str(report.total_processes))
    sys_table.add_row("Startup",   f"{report.startup_count} programs")

    console.print(Panel(sys_table, title="[bold cyan]System Overview[/]", border_style="cyan"))

    # Drives
    drive_table = Table(box=box.ROUNDED, border_style="cyan")
    drive_table.add_column("Drive",    style="bold white", no_wrap=True)
    drive_table.add_column("Total",    style="dim",   justify="right")
    drive_table.add_column("Used",     style="yellow", justify="right")
    drive_table.add_column("Free",     style="green",  justify="right")
    drive_table.add_column("Usage",    justify="left", no_wrap=True)

    for d in report.drives:
        bar_len = 20
        filled = int(d.percent_used / 100 * bar_len)
        color = "red" if d.percent_used > 90 else "yellow" if d.percent_used > 75 else "green"
        bar = f"[{color}]{'█' * filled}[/][dim]{'░' * (bar_len - filled)}[/] {d.percent_used:.0f}%"
        drive_table.add_row(d.drive, d.total_str, d.used_str, d.free_str, bar)

    console.print(Panel(drive_table, title="[bold cyan]Disk Drives[/]", border_style="cyan"))

    # Top processes
    proc_table = Table(box=box.ROUNDED, border_style="cyan", title="Top Processes by RAM")
    proc_table.add_column("PID",     style="dim",   justify="right")
    proc_table.add_column("Name",    style="bold white", no_wrap=True)
    proc_table.add_column("CPU %",   style="yellow", justify="right")
    proc_table.add_column("RAM",     style="cyan",   justify="right")

    for p in report.top_processes[:10]:
        proc_table.add_row(str(p.pid), p.name, f"{p.cpu_percent:.1f}", f"{p.memory_mb:.1f} MB")

    console.print(proc_table)

    # Recommendations
    if report.recommendations:
        recs = "\n".join(f"  • {r}" for r in report.recommendations)
        console.print(Panel(recs, title="[bold yellow]Recommendations[/]", border_style="yellow"))


@app.command()
def wipe(
    path: Path = typer.Argument(..., help="File or directory to securely wipe."),
    passes: int = typer.Option(3, "--passes", "-p", help="Number of overwrite passes (1, 3, 7, 35)."),
    free_space: bool = typer.Option(False, "--free-space", help="Wipe free space on the drive instead."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Securely overwrite and delete files (prevents recovery)."""
    from pcleaner.core.wiper import DriveWiper, WIPE_STANDARDS

    from pcleaner.utils.security import safe_path, validate_wiper_passes, PathTraversalError
    try:
        path = safe_path(path)
        validate_wiper_passes(passes)
    except (PathTraversalError, ValueError) as e:
        console.print(f"[red]Invalid input:[/] {e}")
        raise typer.Exit(1)

    _print_banner()
    standard = WIPE_STANDARDS.get(passes, f"{passes}-pass")
    console.print(f"[bold]Wipe standard:[/] {standard}")

    if not path.exists():
        console.print(f"[red]Path not found:[/] {path}")
        raise typer.Exit(1)

    if not yes:
        action = "wipe free space on" if free_space else "permanently destroy"
        if not Confirm.ask(f"  [red]This will {action} [bold]{path}[/][/]. Continue?"):
            console.print("[dim]Cancelled.[/]")
            return

    wiper = DriveWiper(passes=passes)

    if free_space:
        with console.status(f"Wiping free space on {path}..."):
            ok = wiper.wipe_free_space(str(path))
        console.print("[green]✓ Free space wipe complete.[/]" if ok else "[red]✗ Wipe failed.[/]")
    elif path.is_file():
        with console.status(f"Wiping {path.name}..."):
            ok = wiper.wipe_file(path)
        console.print("[green]✓ File wiped.[/]" if ok else "[red]✗ Wipe failed.[/]")
    elif path.is_dir():
        with console.status(f"Wiping directory {path.name}..."):
            wiped, failed = wiper.wipe_directory(path)
        console.print(f"[green]✓ {wiped} files wiped.[/]" + (f" [red]{failed} failed.[/]" if failed else ""))


@app.command()
def duplicates(
    paths: list[Path] = typer.Argument(..., help="Directories to scan for duplicates."),
    min_size: int = typer.Option(1024, "--min-size", help="Minimum file size in bytes."),
    delete: bool = typer.Option(False, "--delete", "-d", help="Delete duplicates (keeps newest)."),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview only."),
) -> None:
    """Find duplicate files by content (MD5 hash)."""
    from pcleaner.tools.duplicates import DuplicateFinder

    _print_banner()
    finder = DuplicateFinder(min_size=min_size)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console, transient=True) as p:
        task = p.add_task("Scanning for duplicates...")
        finder.set_progress_callback(lambda phase, cur, tot: p.update(task, description=f"{phase}..."))
        result = finder.scan(list(paths))

    if not result.groups:
        console.print("[green]✓ No duplicates found.[/]")
        return

    table = Table(title=f"Duplicate Files ({len(result.groups)} groups)", box=box.ROUNDED, border_style="cyan")
    table.add_column("#",       style="dim",    justify="right")
    table.add_column("Files",   style="white",  justify="right")
    table.add_column("Size",    style="yellow", justify="right")
    table.add_column("Wasted",  style="red",    justify="right")
    table.add_column("Example", style="dim white", no_wrap=True)

    for i, group in enumerate(result.sorted_by_wasted()[:20], 1):
        table.add_row(
            str(i),
            str(len(group.files)),
            group.size_str,
            group.wasted_str,
            str(group.files[0])[:60],
        )

    console.print(table)
    console.print(f"\n  [bold]Total wasted space:[/] [red]{result.total_wasted_str}[/]")
    console.print(f"  [bold]Files scanned:[/] {result.scanned_files}")

    if delete:
        if not dry_run and not Confirm.ask("\n  Delete duplicates (keep newest)?", default=False):
            return
        deleted, errors = finder.delete_duplicates(result.groups, keep="newest", dry_run=dry_run)
        label = "Would delete" if dry_run else "Deleted"
        console.print(f"[green]✓ {label} {deleted} files.[/]")
        if errors:
            console.print(f"[yellow]{errors} files could not be deleted.[/]")


# ---------------------------------------------------------------------------
# Registry sub-commands
# ---------------------------------------------------------------------------

@registry_app.command("scan")
def registry_scan() -> None:
    """Scan the registry for issues."""
    from pcleaner.core.registry import RegistryScanner

    _print_banner()
    console.print("[bold]Scanning registry...[/]\n")
    scanner = RegistryScanner()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console, transient=True) as p:
        task = p.add_task("Scanning...", total=3)
        def _cb(label, cur, tot): p.update(task, description=f"Checking {label}...", completed=cur, total=tot)
        issues = scanner.scan(progress_cb=_cb)

    if not issues:
        console.print("[green]✓ No registry issues found.[/]")
        return

    table = Table(title=f"Registry Issues ({len(issues)})", box=box.ROUNDED, border_style="cyan")
    table.add_column("Type",        style="yellow",    no_wrap=True)
    table.add_column("Key",         style="dim white")
    table.add_column("Description", style="white")

    for issue in issues[:50]:
        table.add_row(issue.issue_type, issue.full_path[:50], issue.description[:60])

    console.print(table)
    if len(issues) > 50:
        console.print(f"  [dim]... and {len(issues) - 50} more issues[/]")
    console.print(f"\n  [bold]Total issues:[/] [yellow]{len(issues)}[/]")
    console.print("  Run [cyan]pcleaner registry clean[/] to fix them.")


@registry_app.command("clean")
def registry_clean(
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview only."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Scan and clean registry issues (auto-backup first)."""
    from pcleaner.core.registry import RegistryScanner, RegistryCleaner

    _print_banner()
    console.print("[bold]Scanning registry...[/]")
    scanner = RegistryScanner()
    with console.status("Scanning..."):
        issues = scanner.scan()

    if not issues:
        console.print("[green]✓ No registry issues to clean.[/]")
        return

    console.print(f"  Found [yellow]{len(issues)}[/] issues.")

    if not dry_run:
        if not yes and not Confirm.ask("  Clean registry? (A backup will be created first)", default=False):
            return

    cleaner = RegistryCleaner()
    if not dry_run:
        backup = cleaner.backup_full()
        if backup:
            console.print(f"  [dim]Backup saved to: {backup}[/]")

    cleaned, errors = cleaner.clean(issues, dry_run=dry_run)
    label = "Would clean" if dry_run else "Cleaned"
    console.print(f"[green]✓ {label} {cleaned} registry entries.[/]")
    if errors:
        console.print(f"[yellow]{errors} entries could not be cleaned.[/]")


# ---------------------------------------------------------------------------
# Startup sub-commands
# ---------------------------------------------------------------------------

@startup_app.command("list")
def startup_list() -> None:
    """List all startup programs."""
    from pcleaner.tools.startup import StartupManager

    _print_banner()
    with console.status("Reading startup entries..."):
        mgr = StartupManager()
        entries = mgr.list_entries()

    if not entries:
        console.print("[dim]No startup entries found.[/]")
        return

    table = Table(title=f"Startup Programs ({len(entries)})", box=box.ROUNDED, border_style="cyan")
    table.add_column("#",       style="dim",   justify="right")
    table.add_column("Name",    style="bold white", no_wrap=True)
    table.add_column("Source",  style="dim cyan")
    table.add_column("Status",  justify="center")
    table.add_column("Command", style="dim white")

    for i, e in enumerate(entries, 1):
        status = "[green]Enabled[/]" if e.enabled else "[red]Disabled[/]"
        table.add_row(str(i), e.name[:30], e.source, status, e.command[:50])

    console.print(table)


@startup_app.command("disable")
def startup_disable(name: str = typer.Argument(..., help="Name of the startup entry to disable.")) -> None:
    """Disable a startup program."""
    _print_banner()
    from pcleaner.tools.startup import StartupManager
    mgr = StartupManager()
    entries = {e.name: e for e in mgr.list_entries()}
    if name not in entries:
        console.print(f"[red]Entry not found:[/] {name}")
        raise typer.Exit(1)
    ok = mgr.disable(entries[name])
    console.print("[green]✓ Disabled.[/]" if ok else "[red]✗ Failed to disable.[/]")


@startup_app.command("enable")
def startup_enable(name: str = typer.Argument(..., help="Name of the startup entry to enable.")) -> None:
    """Enable a startup program."""
    _print_banner()
    from pcleaner.tools.startup import StartupManager
    mgr = StartupManager()
    entries = {e.name: e for e in mgr.list_entries()}
    if name not in entries:
        console.print(f"[red]Entry not found:[/] {name}")
        raise typer.Exit(1)
    ok = mgr.enable(entries[name])
    console.print("[green]✓ Enabled.[/]" if ok else "[red]✗ Failed to enable.[/]")


# ---------------------------------------------------------------------------
# Disk sub-commands
# ---------------------------------------------------------------------------

@disk_app.command("analyze")
def disk_analyze(
    path: Path = typer.Argument(Path.home(), help="Directory to analyze."),
    top: int = typer.Option(10, "--top", "-t", help="Show top N largest directories."),
) -> None:
    """Analyze disk usage by file type."""
    from pcleaner.tools.disk_analyzer import DiskAnalyzer

    _print_banner()
    from pcleaner.utils.security import safe_path, PathTraversalError
    try:
        path = safe_path(path)
    except (PathTraversalError, ValueError) as e:
        console.print(f"[red]Invalid path:[/] {e}")
        raise typer.Exit(1)

    if not path.exists():
        console.print(f"[red]Path not found:[/] {path}")
        raise typer.Exit(1)

    console.print(f"[bold]Analyzing:[/] {path}\n")
    analyzer = DiskAnalyzer()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console, transient=True) as p:
        t = p.add_task("Scanning files...")
        analyzer.set_progress_callback(lambda cur, cnt: p.update(t, description=f"Scanned {cnt} files..."))
        result = analyzer.analyze(path)

    # Categories table
    cat_table = Table(title="Disk Usage by File Type", box=box.ROUNDED, border_style="cyan")
    cat_table.add_column("Category",  style="bold white", no_wrap=True)
    cat_table.add_column("Files",     style="dim",   justify="right")
    cat_table.add_column("Size",      style="yellow", justify="right")
    cat_table.add_column("Share",     justify="left", no_wrap=True)

    for cat in result.sorted_categories():
        if cat.size == 0:
            continue
        pct = result.percent(cat.name)
        bar_len = 20
        filled = int(pct / 100 * bar_len)
        bar = f"[cyan]{'█' * filled}[/][dim]{'░' * (bar_len - filled)}[/] {pct:.1f}%"
        cat_table.add_row(cat.name, str(cat.count), cat.size_str, bar)

    console.print(cat_table)
    console.print(f"\n  [bold]Total:[/] [yellow]{result.total_size_str}[/] in {result.total_files} files\n")

    # Top dirs
    if result.largest_dirs:
        dir_table = Table(title=f"Top {top} Largest Directories", box=box.ROUNDED, border_style="cyan")
        dir_table.add_column("Path",   style="dim white")
        dir_table.add_column("Size",   style="yellow", justify="right")

        for d in result.largest_dirs[:top]:
            dir_table.add_row(str(d.path)[:70], d.size_str)

        console.print(dir_table)
