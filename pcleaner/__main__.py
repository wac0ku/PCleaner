"""Entry point dispatcher for PCleaner.

Usage:
    python -m pcleaner          -> CLI (Typer)
    python -m pcleaner --tui    -> TUI (Textual)
    python -m pcleaner --gui    -> GUI (CustomTkinter)
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


def main() -> None:
    """Main entry point — dispatches to GUI, TUI, or CLI."""
    args = sys.argv[1:]

    if "--gui" in args:
        sys.argv.remove("--gui")
        launch_gui()
        return

    if "--tui" in args:
        sys.argv.remove("--tui")
        launch_tui()
        return

    # Default: Typer CLI
    from pcleaner.cli.commands import app as cli_app
    cli_app()


if __name__ == "__main__":
    main()
