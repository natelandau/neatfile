"""Execute CLI commands."""

import cappa
from rich.prompt import Confirm

from neatfile import settings
from neatfile.features import clean_filename, commit_changes, find_processable_files, sort_file
from neatfile.models import File
from neatfile.utils import console, pp
from neatfile.views import confirmation_table


def execute_command() -> None:
    """Execute the current CLI command.

    Process files based on the current subcommand (clean, sort, or process).
    Handle file operations, confirmations, and commit changes based on settings.

    Raises:
        cappa.Exit: If no changes were made or if user declines to apply changes.
    """
    files_to_process = [File(f) for f in find_processable_files(settings.files)]

    files_with_changes = []
    files_without_changes = []

    for file in files_to_process:
        pp.debug(f"Working on: `{file.display_path}`")

        if settings.subcommand in {"cleancommand", "processcommand"}:
            clean_filename(file)

        if settings.subcommand in {"sortcommand", "processcommand"}:
            file.new_parent = sort_file(file)

        if file.has_changes:
            files_with_changes.append(file)
        else:
            files_without_changes.append(file)

    if not files_with_changes:
        pp.info("No changes made")
        raise cappa.Exit(code=0)

    if settings.confirm_changes and not settings.force:
        console.print(
            confirmation_table(
                files_with_changes,
                total_files=len(files_to_process) + len(files_without_changes),
            )
        )
        if not Confirm.ask("Apply changes"):
            pp.info("Changes not applied")
            raise cappa.Exit(code=0)

    for file in files_with_changes + files_without_changes:
        commit_changes(file)

    raise cappa.Exit(code=0)
