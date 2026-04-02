"""Entry point dispatcher for PCleaner.

Usage:
    python -m pcleaner          -> GUI (default desktop app)
    python -m pcleaner --tui    -> TUI (Textual)
    python -m pcleaner --cli    -> CLI (Typer)
    python -m pcleaner clean    -> CLI subcommand (auto-detected)
"""

from __future__ import annotations

import sys


def launch_gui() -> None:
    """Launch the CustomTkinter GUI."""
    from pcleaner.gui.app import PCleaner as GUIApp
    app = GUIApp()
    app.mainloop()


def launch_tui() -> None:
    """Launch the Textual TUI."""
    from pcleaner.tui.app import PCleanerTUI
    PCleanerTUI().run()


# CLI subcommands that should route to the Typer CLI
_CLI_COMMANDS = {
    "clean", "health", "wipe", "duplicates",
    "registry", "startup", "disk",
    "--help", "-h", "--version", "-V",
}


def main() -> None:
    """Main entry point — defaults to GUI, CLI only when explicitly requested."""
    args = sys.argv[1:]

    # Explicit interface flags
    if "--gui" in args:
        sys.argv.remove("--gui")
        launch_gui()
        return

    if "--tui" in args:
        sys.argv.remove("--tui")
        launch_tui()
        return

    if "--cli" in args:
        sys.argv.remove("--cli")
        from pcleaner.cli.commands import app as cli_app
        cli_app()
        return

    # Auto-detect CLI subcommands (so `pcleaner clean` still works)
    if args and args[0] in _CLI_COMMANDS:
        from pcleaner.cli.commands import app as cli_app
        cli_app()
        return

    # Default: launch GUI (desktop app)
    launch_gui()


if __name__ == "__main__":
    main()
