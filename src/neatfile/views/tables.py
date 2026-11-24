"""Rich tables for the neatfile package."""

from collections.abc import Sequence
from pathlib import Path

from nclutils import pp
from rich import box
from rich.table import Table
from rich.text import Text

from neatfile.models import File
from neatfile.utils.paths import display_path


def confirmation_table(
    files: list[File], total_files: int | None = None, *, project_path: Path | None = None
) -> Table:
    """Build a table of pending changes for the user to confirm.

    Args:
        files (list[File]): List of files to process.
        total_files (int | None, optional): Total number of files to process. Defaults to None.
        project_path (Path | None, optional): Root of the project files move into. Shows a new path column when set. Defaults to None.

    Returns:
        Table: Confirmation table.
    """
    organized_files = bool(project_path and [x for x in files if x.has_new_parent])

    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold",
        min_width=40,
        title=f"Pending changes for {len(files)} of {total_files} files"
        if total_files
        else f"Pending changes for {len(files)} files",
    )

    table.add_column("#")
    table.add_column("Original Name", overflow="fold")
    table.add_column("New Name", overflow="fold")
    if organized_files:
        table.add_column("New Path", overflow="fold")
    else:
        table.add_column("")
    if pp.get_default().verbosity >= 1:
        table.add_column("Diff", overflow="fold")

    for _n, file in enumerate(files, start=1):
        table.add_row(
            str(_n),
            Text(file.name),
            Text(file.new_name) if file.has_new_name else "[green]No Changes[/green]",
            Text("…/" + str(file.new_parent.relative_to(project_path)) + "/")
            if organized_files and file.has_new_parent
            else "",
            file.get_filename_diff()
            if pp.get_default().verbosity >= 1 and file.has_new_name
            else "",
        )

    return table


def undo_table(moves: Sequence[tuple[Path, Path]]) -> Table:
    """Build a table of the files undo will move back, so the user can review them before confirming.

    Args:
        moves (Sequence[tuple[Path, Path]]): Each file's current path and the path it returns to.

    Returns:
        Table: One row per file, with its current path and the path it returns to.
    """
    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold",
        min_width=40,
        title=f"Files to restore from the last run: {len(moves)}",
    )
    table.add_column("#")
    table.add_column("Current path", overflow="fold")
    table.add_column("Restore to", overflow="fold")

    for number, (current_path, restore_to) in enumerate(moves, start=1):
        table.add_row(
            str(number),
            Text(str(display_path(current_path))),
            Text(str(display_path(restore_to))),
        )

    return table
