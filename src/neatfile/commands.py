"""Execute CLI commands."""

from enum import StrEnum
from pathlib import Path

import cappa
from nclutils import pp
from rich.prompt import Confirm

from neatfile.config import Config, RunOptions
from neatfile.features import clean_filename, commit_changes, find_processable_files, sort_file
from neatfile.models import File, Project
from neatfile.views import confirmation_table

NO_CHANGES_MESSAGE = "No changes made"
CONFIRMATION_NO_INPUT_MESSAGE = "Cannot confirm changes because stdin has no input. Run neatfile in an interactive terminal, pipe the answer (y or n), or add --force to skip confirmation."


class Mode(StrEnum):
    """Select which steps `execute_command` runs on each file."""

    CLEAN = "clean"
    SORT = "sort"
    PROCESS = "process"


def _user_approves(
    files_with_changes: list[File],
    *,
    total_files: int,
    options: RunOptions,
    project_path: Path | None,
) -> bool:
    """Show the pending changes and ask the user to apply them.

    Args:
        files_with_changes (list[File]): Files whose name or parent will change.
        total_files (int): Number of files processed, shown in the table summary.
        options (RunOptions): The run options that decide whether to ask.
        project_path (Path | None): Root of the project files move into, if any.

    Returns:
        bool: True when confirmation is not required or the user accepts.

    Raises:
        cappa.Exit: If stdin has no input for the confirmation prompt.
    """
    if not options.confirm_changes or options.force:
        return True

    pp.console().print(
        confirmation_table(
            files=files_with_changes, total_files=total_files, project_path=project_path
        )
    )
    try:
        return bool(Confirm.ask("Apply changes"))
    except EOFError:
        pp.error(CONFIRMATION_NO_INPUT_MESSAGE)
        raise cappa.Exit(code=1) from None


def _plan_changes(
    file: File,
    *,
    config: Config,
    options: RunOptions,
    clean: bool,
    sort_project: Project | None,
) -> bool:
    """Set the file's new name and parent for the steps this run takes.

    Args:
        file (File): The file to plan changes for.
        config (Config): The settings for this run.
        options (RunOptions): The CLI-only values for this run.
        clean (bool): Whether to clean the filename.
        sort_project (Project | None): The project to sort the file into, or None to skip sorting.

    Returns:
        bool: False when sorting found no folder for the file, True otherwise.
    """
    if clean:
        clean_filename(file=file, config=config, date=options.date, date_only=options.date_only)

    if sort_project is not None:
        new_parent = sort_file(file=file, project=sort_project, user_terms=config.user_terms)
        if new_parent is None:
            return False
        file.new_parent = new_parent

    return True


def execute_command(
    *, mode: Mode, config: Config, options: RunOptions, project: Project | None
) -> None:
    """Clean, sort, or clean and sort the files named on the command line, then apply the changes.

    Args:
        mode (Mode): Which steps to run on each file.
        config (Config): The settings for this run.
        options (RunOptions): The CLI-only values for this run.
        project (Project | None): The project files are sorted into. Required for `Mode.SORT` and `Mode.PROCESS`.

    Raises:
        ValueError: If `mode` sorts files and `project` is None.
        cappa.Exit: Always, once processing ends. The code is non-zero when any file could not be sorted.
    """
    sort_project: Project | None = None
    if mode in {Mode.SORT, Mode.PROCESS}:
        if project is None:
            msg = f"Mode `{mode}` sorts files and needs a project, but project is None"
            raise ValueError(msg)
        sort_project = project

    files_to_process = [
        File(f)
        for f in find_processable_files(
            options.files, config=config, max_depth=options.file_search_depth
        )
    ]
    project_path = project.path if project else None

    planned_files: list[File] = []
    unmatched_count = 0

    for file in files_to_process:
        pp.debug(f"Working on: `{file.display_path}`")

        # Skip an unsorted file rather than abort so the rest of the batch still gets sorted
        if not _plan_changes(
            file,
            config=config,
            options=options,
            clean=mode in {Mode.CLEAN, Mode.PROCESS},
            sort_project=sort_project,
        ):
            unmatched_count += 1
            continue
        planned_files.append(file)

    exit_code = 1 if unmatched_count else 0
    files_with_changes = [file for file in planned_files if file.has_changes]

    if not files_with_changes:
        pp.info(NO_CHANGES_MESSAGE)
        raise cappa.Exit(code=exit_code)

    if not _user_approves(
        files_with_changes=files_with_changes,
        total_files=len(files_to_process),
        options=options,
        project_path=project_path,
    ):
        pp.info("Changes not applied")
        raise cappa.Exit(code=exit_code)

    # Report changed files before the unchanged ones; the sort is stable within each group
    for file in sorted(planned_files, key=lambda planned: not planned.has_changes):
        commit_changes(
            file=file,
            dry_run=options.dry_run,
            keep_backup=not config.overwrite_existing,
            project_path=project_path,
        )

    if unmatched_count:
        pp.warning(f"{unmatched_count} file(s) could not be sorted")

    raise cappa.Exit(code=exit_code)
