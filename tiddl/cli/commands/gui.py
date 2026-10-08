import typer


gui_command = typer.Typer(
    name="gui", help="Open the desktop interface for album downloads."
)


@gui_command.callback(invoke_without_command=True)
def open_gui():
    # Keep the normal CLI usable in minimal/headless Python installations.
    from tiddl.gui import run_gui

    run_gui()
