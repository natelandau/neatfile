"""Rich tables for the neatfile package."""

from nclutils import pp
from rich import box
from rich.table import Table

from neatfile import settings
from neatfile.models import File


def confirmation_table(files: list[File], total_files: int | None = None) -> Table:
    """Display a confirmation table to the user.

    Args:
        files (list[File]): List of files to process.
        total_files (int): Total number of files to process.

    Returns:
        Table: Confirmation table.
    """
    project_path = None if not settings.get("project", None) else settings.project.path

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
    if pp.is_debug:
        table.add_column("Diff", overflow="fold")

    for _n, file in enumerate(files, start=1):
        table.add_row(
            str(_n),
            file.name,
            file.new_name if file.has_new_name else "[green]No Changes[/green]",
            str("…/" + str(file.new_parent.relative_to(project_path)) + "/")
            if organized_files and file.has_new_parent
            else "",
            file.get_filename_diff() if pp.is_debug and file.has_new_name else "",
        )

    return table
