"""Execute CLI commands."""

import cappa
from nclutils import pp
from rich.prompt import Confirm

from neatfile import settings
from neatfile.features import clean_filename, commit_changes, find_processable_files, sort_file
from neatfile.models import File
from neatfile.views import confirmation_table


def _user_approves(files_with_changes: list[File], total_files: int) -> bool:
    """Show the pending changes and ask the user to apply them.

    Args:
        files_with_changes (list[File]): Files whose name or parent will change.
        total_files (int): Number of files processed, shown in the table summary.

    Returns:
        bool: True when confirmation is not required or the user accepts.
    """
    if not settings.confirm_changes or settings.force:
        return True

    pp.console().print(confirmation_table(files_with_changes, total_files=total_files))
    return bool(Confirm.ask("Apply changes"))


def execute_command() -> None:
    """Execute the current CLI command.

    Process files based on the current subcommand (clean, sort, or process).
    Handle file operations, confirmations, and commit changes based on settings.

    Raises:
        cappa.Exit: Always, once processing ends. The code is non-zero when any file could not be sorted.
    """
    files_to_process = [File(f) for f in find_processable_files(settings.files)]

    files_with_changes = []
    files_without_changes = []
    unmatched_count = 0

    for file in files_to_process:
        pp.debug(f"Working on: `{file.display_path}`")

        if settings.subcommand in {"cleancommand", "processcommand"}:
            clean_filename(file)

        if settings.subcommand in {"sortcommand", "processcommand"}:
            new_parent = sort_file(file)
            # Skip the file rather than abort so the rest of the batch still gets sorted
            if new_parent is None:
                unmatched_count += 1
                continue
            file.new_parent = new_parent

        if file.has_changes:
            files_with_changes.append(file)
        else:
            files_without_changes.append(file)

    exit_code = 1 if unmatched_count else 0

    if not files_with_changes:
        pp.info("No changes made")
        raise cappa.Exit(code=exit_code)

    if not _user_approves(
        files_with_changes, total_files=len(files_to_process) + len(files_without_changes)
    ):
        pp.info("Changes not applied")
        raise cappa.Exit(code=exit_code)

    for file in files_with_changes + files_without_changes:
        commit_changes(file)

    if unmatched_count:
        pp.warning(f"{unmatched_count} file(s) could not be sorted")

    raise cappa.Exit(code=exit_code)
