"""PCleaner TUI — modern sidebar navigation interface built with Textual."""

from __future__ import annotations

from pathlib import Path

_CSS_PATH = Path(__file__).parent / "pcleaner.tcss"

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Label, Static

from pcleaner import APP_FULL_NAME, APP_TAGLINE, __version__
from pcleaner.utils.elevation import is_admin


# ---------------------------------------------------------------------------
# Confirm modal
# ---------------------------------------------------------------------------

class ConfirmModal(ModalScreen):
    """A styled yes/no confirmation dialog."""

    def __init__(self, message: str, title: str = "Confirm") -> None:
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Container(id="modal-dialog"):
            yield Static(f"  [bold cyan]⚠  {self._title}[/]", id="modal-title")
            yield Static(f"\n  {self._message}\n", id="modal-body")
            with Horizontal(id="modal-buttons"):
                yield Button("  Yes  ", id="btn-yes", variant="error")
                yield Button("  No   ", id="btn-no", variant="default")

    @on(Button.Pressed, "#btn-yes")
    def confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn-no")
    def cancel(self) -> None:
        self.dismiss(False)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

_NAV_ITEMS = [
    ("dashboard",   "🏠", "Dashboard",   "1"),
    ("cleaner",     "🧹", "Cleaner",     "2"),
    ("registry",    "🗂", "Registry",    "3"),
    ("startup",     "🚀", "Startup",     "4"),
    ("uninstaller", "📦", "Uninstaller", "5"),
    ("disk",        "💽", "Disk",        "6"),
    ("duplicates",  "🔍", "Duplicates",  "7"),
    ("health",      "❤", "Health",      "8"),
    ("taskmanager", "🛡", "Task Mgr",    "9"),
]

_NAV_IDS = [item[0] for item in _NAV_ITEMS]


class SidebarButton(Button):
    """A sidebar navigation button with icon + label."""

    def __init__(self, nav_id: str, icon: str, label: str, hotkey: str) -> None:
        display = f" {icon}  {label:<12} [dim]{hotkey}[/]"
        super().__init__(display, id=f"nav-{nav_id}", classes="sidebar-btn")
        self.nav_id = nav_id


class Sidebar(Container):
    """Left sidebar with navigation and quick actions."""

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold cyan]  PCleaner[/]\n"
            f"  [dim]v{__version__}[/]",
            id="sidebar-logo",
        )
        yield Static("  [dim]─── Navigation ───[/]", classes="sidebar-divider")

        for nav_id, icon, label, hotkey in _NAV_ITEMS:
            yield SidebarButton(nav_id, icon, label, hotkey)

        yield Static("", classes="sidebar-spacer")
        yield Static("  [dim]─── Quick Actions ──[/]", classes="sidebar-divider")
        yield Button(" ⚡ Flush DNS", id="btn-quick-dns", classes="sidebar-quick-btn")
        yield Button(" 📎 Clear Clipboard", id="btn-quick-clipboard", classes="sidebar-quick-btn")

        # Admin status indicator
        yield Static("  [dim]─── Privileges ─────[/]", classes="sidebar-divider")
        if is_admin():
            yield Static(
                "  [bold green]✓ Running as Admin[/]",
                id="admin-status",
                classes="admin-badge",
            )
        else:
            yield Static(
                "  [yellow]⚠ Limited privileges[/]",
                id="admin-status",
                classes="admin-badge",
            )
            yield Button(" 🛡 Run as Admin", id="btn-elevate", classes="sidebar-quick-btn")

        yield Static(
            "\n  [dim green]✓ Open Source[/]\n  [dim green]✓ MIT License[/]",
            id="sidebar-footer",
        )


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class PCleanerTUI(App):
    """PCleaner Terminal UI with sidebar navigation."""

    CSS_PATH = _CSS_PATH
    TITLE = APP_FULL_NAME
    SUB_TITLE = f"v{__version__} — {APP_TAGLINE}"

    BINDINGS = [
        Binding("q",       "quit",            "Quit",        show=True),
        Binding("ctrl+c",  "quit",            "Quit",        show=False),
        # Number keys — shown in footer
        Binding("1",       "nav_dashboard",   "Dashboard",   show=True),
        Binding("2",       "nav_cleaner",     "Cleaner",     show=True),
        Binding("3",       "nav_registry",    "Registry",    show=True),
        Binding("4",       "nav_startup",     "Startup",     show=True),
        Binding("5",       "nav_uninstaller", "Uninstaller", show=True),
        Binding("6",       "nav_disk",        "Disk",        show=True),
        Binding("7",       "nav_duplicates",  "Duplicates",  show=True),
        Binding("8",       "nav_health",      "Health",      show=True),
        Binding("9",       "nav_taskmanager", "Task Mgr",    show=True),
        # F-keys — hidden fallback
        Binding("f1",      "nav_dashboard",   "Dashboard",   show=False),
        Binding("f2",      "nav_cleaner",     "Cleaner",     show=False),
        Binding("f3",      "nav_registry",    "Registry",    show=False),
        Binding("f4",      "nav_startup",     "Startup",     show=False),
        Binding("f5",      "nav_uninstaller", "Uninstaller", show=False),
        Binding("f6",      "nav_disk",        "Disk",        show=False),
        Binding("f7",      "nav_duplicates",  "Duplicates",  show=False),
        Binding("f8",      "nav_health",      "Health",      show=False),
        Binding("f9",      "nav_taskmanager", "Task Mgr",    show=False),
        # Arrow keys — sidebar navigation
        Binding("up",      "nav_prev",        "Prev",        show=False),
        Binding("down",    "nav_next",        "Next",        show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._current_nav = "dashboard"
        self._nav_index = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "[bold cyan] PCleaner[/bold cyan] [dim]— the free Cleaner App[/dim]  "
            "[green]✓ CCleaner Pro replacement  ✓ Open Source  ✓ MIT[/green]",
            id="top-banner",
        )
        with Horizontal(id="main-layout"):
            yield Sidebar(id="sidebar")
            with ScrollableContainer(id="content-area"):
                pass  # screens are mounted dynamically
        yield Footer()

    def on_mount(self) -> None:
        self._navigate_to("dashboard")

    # ---- Navigation ----

    def _navigate_to(self, nav_id: str) -> None:
        if nav_id in _NAV_IDS:
            self._nav_index = _NAV_IDS.index(nav_id)

        if nav_id == self._current_nav:
            content = self.query_one("#content-area")
            if not content.children:
                self._mount_screen(nav_id)
            return

        self._current_nav = nav_id

        # Update sidebar active states
        for btn in self.query(".sidebar-btn"):
            if isinstance(btn, SidebarButton):
                if btn.nav_id == nav_id:
                    btn.add_class("-active")
                else:
                    btn.remove_class("-active")

        self._mount_screen(nav_id)

    def _mount_screen(self, nav_id: str) -> None:
        content = self.query_one("#content-area")

        for child in list(content.children):
            child.remove()

        content.mount(self._create_screen(nav_id))

    def _create_screen(self, nav_id: str) -> Container:
        if nav_id == "dashboard":
            from pcleaner.tui.screens.dashboard import DashboardScreen
            return DashboardScreen()
        elif nav_id == "cleaner":
            from pcleaner.tui.screens.cleaner import CleanerScreen
            return CleanerScreen()
        elif nav_id == "registry":
            from pcleaner.tui.screens.registry import RegistryScreen
            return RegistryScreen()
        elif nav_id == "startup":
            from pcleaner.tui.screens.startup import StartupScreen
            return StartupScreen()
        elif nav_id == "uninstaller":
            from pcleaner.tui.screens.uninstaller import UninstallerScreen
            return UninstallerScreen()
        elif nav_id == "disk":
            from pcleaner.tui.screens.disk import DiskScreen
            return DiskScreen()
        elif nav_id == "duplicates":
            from pcleaner.tui.screens.duplicates import DuplicatesScreen
            return DuplicatesScreen()
        elif nav_id == "health":
            from pcleaner.tui.screens.health import HealthScreen
            return HealthScreen()
        elif nav_id == "taskmanager":
            from pcleaner.tui.screens.task_manager import TaskManagerScreen
            return TaskManagerScreen()
        else:
            return Container(Static(f"[red]Unknown screen: {nav_id}[/]"))

    # ---- Sidebar button handler ----

    @on(Button.Pressed, ".sidebar-btn")
    def sidebar_clicked(self, event: Button.Pressed) -> None:
        btn = event.button
        if isinstance(btn, SidebarButton):
            self._navigate_to(btn.nav_id)

    # ---- Quick actions ----

    @on(Button.Pressed, "#btn-quick-dns")
    def quick_dns(self) -> None:
        self._flush_dns()

    @on(Button.Pressed, "#btn-quick-clipboard")
    def quick_clipboard(self) -> None:
        self._clear_clipboard()

    @on(Button.Pressed, "#btn-elevate")
    def elevate(self) -> None:
        self.push_screen(
            ConfirmModal(
                "This will close the app and re-open it with\nadministrator privileges.\n\nContinue?",
                "Request Admin Rights",
            ),
            self._on_confirm_elevate,
        )

    def _on_confirm_elevate(self, confirmed: bool) -> None:
        if confirmed:
            from pcleaner.utils.elevation import request_elevation
            request_elevation()

    @work(thread=True)
    def _flush_dns(self) -> None:
        from pcleaner.utils.security import run_safe
        try:
            run_safe(["ipconfig", "/flushdns"], timeout=10)
            self.call_from_thread(self.notify, "DNS cache flushed ✓", severity="information")
        except Exception as e:
            self.call_from_thread(self.notify, f"DNS flush failed: {e}", severity="error")

    @work(thread=True)
    def _clear_clipboard(self) -> None:
        from pcleaner.utils.security import run_powershell
        try:
            run_powershell("Set-Clipboard -Value $null", timeout=5)
            self.call_from_thread(self.notify, "Clipboard cleared ✓", severity="information")
        except Exception as e:
            self.call_from_thread(self.notify, f"Clipboard clear failed: {e}", severity="error")

    # ---- Number-key / F-key navigation actions ----

    def action_nav_dashboard(self)   -> None: self._navigate_to("dashboard")
    def action_nav_cleaner(self)     -> None: self._navigate_to("cleaner")
    def action_nav_registry(self)    -> None: self._navigate_to("registry")
    def action_nav_startup(self)     -> None: self._navigate_to("startup")
    def action_nav_uninstaller(self) -> None: self._navigate_to("uninstaller")
    def action_nav_disk(self)        -> None: self._navigate_to("disk")
    def action_nav_duplicates(self)  -> None: self._navigate_to("duplicates")
    def action_nav_health(self)      -> None: self._navigate_to("health")
    def action_nav_taskmanager(self) -> None: self._navigate_to("taskmanager")

    # ---- Arrow key sidebar navigation ----

    def action_nav_prev(self) -> None:
        self._nav_index = (self._nav_index - 1) % len(_NAV_IDS)
        self._navigate_to(_NAV_IDS[self._nav_index])

    def action_nav_next(self) -> None:
        self._nav_index = (self._nav_index + 1) % len(_NAV_IDS)
        self._navigate_to(_NAV_IDS[self._nav_index])
