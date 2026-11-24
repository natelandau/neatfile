"""Execute CLI commands."""

from collections.abc import Iterable, Sequence
from datetime import datetime
from enum import StrEnum
from functools import partial
from pathlib import Path

import cappa
from datefind import FoundDate
from nclutils import pp
from rich.prompt import Confirm

from neatfile.config import Config, RunOptions
from neatfile.features import (
    CleanedName,
    CommittedChange,
    JournalEntry,
    JournalReadError,
    JournalWriteError,
    RunRecorder,
    UndoError,
    UndoOutcome,
    UndoResult,
    clean_name,
    commit_changes,
    file_creation_date,
    find_processable_files,
    journal_lock,
    journal_path,
    new_run_id,
    newest_run,
    parse_date_option,
    preview_newest_run,
    read_journal,
    sort_file,
    trim_journal,
    undo_newest_run,
    with_backup_location,
)
from neatfile.models import File, Project
from neatfile.utils.paths import display_path
from neatfile.views import confirmation_table, undo_table

NO_CHANGES_MESSAGE = "No changes made"
CHANGES_NOT_APPLIED_MESSAGE = "Changes not applied"
CONFIRMATION_NO_INPUT_MESSAGE = "Cannot confirm changes because stdin has no input. Run neatfile in an interactive terminal, pipe the answer (y or n), or add --force to skip confirmation."
JOURNAL_WRITE_FAILED_MESSAGE = "{error}. {source} was moved to {destination} but not recorded, so undo cannot reverse it. No more files were changed."
JOURNAL_DAMAGED_LINES_DROPPED_MESSAGE = (
    "Removed unreadable lines {line_numbers} from the undo journal at {path}"
)
JOURNAL_DAMAGED_LINES_IGNORED_MESSAGE = "Ignoring unreadable lines {line_numbers} in the undo journal at {path}. The next change to the journal, by undo or by a run that renames or moves files, removes them"
NOTHING_TO_UNDO_MESSAGE = "Nothing to undo"
JOURNAL_CHANGED_MESSAGE = "The undo journal at {path} changed while undo waited for confirmation. No files were changed. Run neatfile undo again to see the newest run"
UNDO_OUTCOME_MESSAGES: dict[UndoOutcome, str] = {
    UndoOutcome.RESTORED: "restored",
    UndoOutcome.ORIGINAL_NAME_TAKEN: "skipped, another file has the original name",
    UndoOutcome.FOLDER_MISSING: "skipped, folder not found. Kept in the journal for a later undo",
    UndoOutcome.NOT_FOUND: "not found, removed from the journal",
}
UNDO_BACKUP_RESTORED_MESSAGE = "the replaced file returned from backup {backup} to {destination}"
UNDO_BACKUP_WOULD_RETURN_MESSAGE = (
    "the replaced file would return from backup {backup} to {destination}"
)


class Mode(StrEnum):
    """Select which steps `execute_command` runs on each file."""

    CLEAN = "clean"
    SORT = "sort"
    PROCESS = "process"

    @property
    def cleans(self) -> bool:
        """Report whether this mode cleans filenames."""
        return self in {Mode.CLEAN, Mode.PROCESS}

    @property
    def sorts(self) -> bool:
        """Report whether this mode sorts files into a project."""
        return self in {Mode.SORT, Mode.PROCESS}


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
    return _ask_to_apply()


def _ask_to_apply() -> bool:
    """Ask the user to apply the changes shown above, failing cleanly when stdin has no input.

    Returns:
        bool: True when the user accepts.

    Raises:
        cappa.Exit: If stdin has no input for the confirmation prompt.
    """
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
    override_date: FoundDate | None,
    sort_project: Project | None,
) -> bool:
    """Set the file's new name and parent for the steps this run takes.

    Args:
        file (File): The file to plan changes for.
        config (Config): The settings for this run.
        options (RunOptions): The CLI-only values for this run.
        clean (bool): Whether to clean the filename.
        override_date (FoundDate | None): The date from `--date` to give every cleaned file, or None.
        sort_project (Project | None): The project to sort the file into, or None to skip sorting.

    Returns:
        bool: False when sorting found no folder for the file, True otherwise.
    """
    pp.debug(f"Working on: `{file.display_path}`")

    if clean:
        cleaned: CleanedName = clean_name(
            stem=file.stem,
            suffix=file.suffix,
            config=config,
            override_date=override_date,
            date_only=options.date_only,
            fallback_date=partial(file_creation_date, file.path, tz=config.tz),
        )
        file.new_stem = cleaned.stem
        file.new_suffix = cleaned.suffix

    if sort_project is not None:
        new_parent = sort_file(file=file, project=sort_project, user_terms=config.user_terms)
        if new_parent is None:
            return False
        file.new_parent = new_parent

    return True


def _open_run_recorder(*, config: Config, options: RunOptions) -> RunRecorder | None:
    """Open the undo journal before any file moves, so an unwritable journal stops the run unchanged.

    Args:
        config (Config): The settings for this run.
        options (RunOptions): The CLI-only values for this run.

    Returns:
        RunRecorder | None: The open recorder, or None on a dry run or when the journal is turned off.

    Raises:
        cappa.Exit: If the journal cannot be created or opened.
    """
    if options.dry_run or config.undo_history_runs == 0:
        return None

    recorder = RunRecorder(path=journal_path(), run_id=new_run_id(datetime.now().astimezone()))
    try:
        recorder.prepare()
    except JournalWriteError as error:
        pp.error(str(error))
        raise cappa.Exit(code=1) from None
    return recorder


def _close_run_recorder(recorder: RunRecorder) -> bool:
    """Close the undo journal, reporting a failure rather than raising it, so closing never hides an error already ending the run.

    Args:
        recorder (RunRecorder): The recorder opened for this run.

    Returns:
        bool: True when the journal closed cleanly.
    """
    try:
        recorder.close()
    except JournalWriteError as error:
        pp.error(str(error))
        return False
    return True


def _commit_and_record(
    files: Iterable[File],
    *,
    recorder: RunRecorder | None,
    options: RunOptions,
    keep_backup: bool,
    project_path: Path | None,
) -> list[CommittedChange]:
    """Commit each file and record it in the undo journal as soon as it moves.

    Recording each file right away keeps the journal accurate if the run is interrupted.

    Args:
        files (Iterable[File]): Files to commit, in the order to report them.
        recorder (RunRecorder | None): The open journal recorder, or None when nothing is recorded.
        options (RunOptions): The CLI-only values for this run.
        keep_backup (bool): Back up a file that a new name would overwrite.
        project_path (Path | None): Root of the project files move into, if any.

    Returns:
        list[CommittedChange]: The changes made.

    Raises:
        cappa.Exit: If a change cannot be recorded. No later file is changed.
    """
    changes: list[CommittedChange] = []
    for file in files:
        change = commit_changes(
            file=file,
            dry_run=options.dry_run,
            keep_backup=keep_backup,
            project_path=project_path,
        )
        if change is None:
            continue
        changes.append(change)
        if recorder is None:
            continue
        try:
            recorder.record(
                source=change.source, destination=change.destination, backup=change.backup
            )
        except JournalWriteError as error:
            message = JOURNAL_WRITE_FAILED_MESSAGE.format(
                error=error, source=change.source, destination=change.destination
            )
            pp.error(
                with_backup_location(
                    message=message, destination=change.destination, backup=change.backup
                )
            )
            raise cappa.Exit(code=1) from None
    return changes


def _trim_run_journal(*, max_runs: int) -> bool:
    """Cap the undo journal at the configured number of runs, deleting it when the cap is 0.

    Args:
        max_runs (int): Number of newest runs to keep.

    Returns:
        bool: True when the journal was trimmed.
    """
    path = journal_path()
    try:
        dropped_line_numbers = trim_journal(path=path, max_runs=max_runs)
    except (JournalReadError, JournalWriteError) as error:
        pp.error(str(error))
        return False

    if dropped_line_numbers:
        pp.warning(
            JOURNAL_DAMAGED_LINES_DROPPED_MESSAGE.format(
                line_numbers=", ".join(str(number) for number in dropped_line_numbers),
                path=path,
            )
        )
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
        cappa.Exit: Always, once processing ends. The code is non-zero when any file could not be sorted or the undo journal could not be written.
    """
    sort_project: Project | None = None
    if mode.sorts:
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
    project_path: Path | None = project.path if project else None

    override_date: FoundDate | None = (
        parse_date_option(options.date, config=config) if mode.cleans else None
    )

    # Skip an unsorted file rather than abort so the rest of the batch still gets sorted
    planned_files: list[File] = [
        file
        for file in files_to_process
        if _plan_changes(
            file=file,
            config=config,
            options=options,
            clean=mode.cleans,
            override_date=override_date,
            sort_project=sort_project,
        )
    ]
    unmatched_count: int = len(files_to_process) - len(planned_files)

    exit_code: int = 1 if unmatched_count else 0
    files_with_changes: list[File] = [file for file in planned_files if file.has_changes]

    if not files_with_changes:
        pp.info(NO_CHANGES_MESSAGE)
        raise cappa.Exit(code=exit_code)

    if not _user_approves(
        files_with_changes=files_with_changes,
        total_files=len(files_to_process),
        options=options,
        project_path=project_path,
    ):
        pp.info(CHANGES_NOT_APPLIED_MESSAGE)
        raise cappa.Exit(code=exit_code)

    recorder = _open_run_recorder(config=config, options=options)
    try:
        changes = _commit_and_record(
            # Report changed files before the unchanged ones; the sort is stable within each group
            sorted(planned_files, key=lambda planned: not planned.has_changes),
            recorder=recorder,
            options=options,
            keep_backup=not config.overwrite_existing,
            project_path=project_path,
        )
    finally:
        if recorder is not None and not _close_run_recorder(recorder):
            exit_code = 1

    if changes and not _trim_run_journal(max_runs=config.undo_history_runs):
        exit_code = 1

    if unmatched_count:
        pp.warning(f"{unmatched_count} file(s) could not be sorted")

    raise cappa.Exit(code=exit_code)


def _describe_undo(result: UndoResult, *, predicted: bool) -> str:
    """Describe one entry's undo outcome, naming every path so the user can find each file.

    Args:
        result (UndoResult): What happened, or would happen, to the entry.
        predicted (bool): Whether the result is a dry-run prediction rather than a completed undo.

    Returns:
        str: One line for the report.
    """
    entry = result.entry
    destination = display_path(entry.destination)
    description = (
        f"{destination} -> {display_path(entry.source)}: {UNDO_OUTCOME_MESSAGES[result.outcome]}"
    )
    if not result.backup_restored or entry.backup is None:
        return description
    backup_message = UNDO_BACKUP_WOULD_RETURN_MESSAGE if predicted else UNDO_BACKUP_RESTORED_MESSAGE
    return f"{description}; {backup_message.format(backup=display_path(entry.backup), destination=destination)}"


def _report_undo_results(results: Sequence[UndoResult]) -> int:
    """Show each restored, skipped, or removed file.

    Args:
        results (Sequence[UndoResult]): The outcome of each entry undone.

    Returns:
        int: 0 when every file was restored, otherwise 1.
    """
    exit_code = 0
    for result in results:
        message = _describe_undo(result, predicted=False)
        if result.outcome == UndoOutcome.RESTORED:
            pp.success(message)
        else:
            pp.warning(message)
            exit_code = 1
    return exit_code


def _preview_undo(entries: Sequence[JournalEntry]) -> None:
    """Show what undo would do with each entry of the newest run, in the same order as the real undo.

    Args:
        entries (Sequence[JournalEntry]): Every readable journal entry, in file order.

    Raises:
        cappa.Exit: If a path cannot be checked.
    """
    try:
        results = preview_newest_run(entries)
    except UndoError as error:
        for result in error.results:
            pp.dryrun(_describe_undo(result, predicted=True))
        pp.error(str(error))
        raise cappa.Exit(code=1) from None
    for result in results:
        pp.dryrun(_describe_undo(result, predicted=True))


def _undo_confirmed_run(*, path: Path, confirmed: Sequence[JournalEntry]) -> tuple[UndoResult, ...]:
    """Revert the newest run while holding the journal lock, if it is still the run the user confirmed.

    Another neatfile process can change the journal while the user reads the prompt, so the journal
    is read again under the lock before any file moves.

    Args:
        path (Path): Journal file.
        confirmed (Sequence[JournalEntry]): The entries of the run the user agreed to revert.

    Returns:
        tuple[UndoResult, ...]: One result per entry of the run, in the order they were processed.

    Raises:
        cappa.Exit: If the journal cannot be locked or read, or its newest run changed.
        UndoError: If a file or the journal cannot be checked or updated.
    """
    try:
        with journal_lock(path):
            contents = read_journal(path)
            if newest_run(contents.entries) != tuple(confirmed):
                pp.error(JOURNAL_CHANGED_MESSAGE.format(path=path))
                raise cappa.Exit(code=1)
            return undo_newest_run(contents.entries, path=path)
    except (JournalReadError, JournalWriteError) as error:
        pp.error(str(error))
        raise cappa.Exit(code=1) from None


def execute_undo(*, dry_run: bool, force: bool) -> None:
    """Revert the newest run in the undo journal after showing the files and asking the user.

    Undo always asks, whatever `confirm_changes` says, because it can move as many files as the run did.

    Args:
        dry_run (bool): Show what undo would do and change nothing.
        force (bool): Restore without asking.

    Raises:
        cappa.Exit: Always. The code is non-zero when the journal cannot be read or written, a file
            cannot be moved back, or any file is skipped or not found.
    """
    path = journal_path()
    try:
        contents = read_journal(path)
    except JournalReadError as error:
        pp.error(str(error))
        raise cappa.Exit(code=1) from None

    if contents.damaged_line_numbers:
        pp.warning(
            JOURNAL_DAMAGED_LINES_IGNORED_MESSAGE.format(
                line_numbers=", ".join(str(number) for number in contents.damaged_line_numbers),
                path=path,
            )
        )

    entries = newest_run(contents.entries)
    if not entries:
        pp.info(NOTHING_TO_UNDO_MESSAGE)
        raise cappa.Exit(code=0)

    pp.console().print(undo_table([(entry.destination, entry.source) for entry in entries]))

    if dry_run:
        _preview_undo(contents.entries)
        raise cappa.Exit(code=0)

    if not force and not _ask_to_apply():
        pp.info(CHANGES_NOT_APPLIED_MESSAGE)
        raise cappa.Exit(code=0)

    try:
        results = _undo_confirmed_run(path=path, confirmed=entries)
    except UndoError as error:
        _report_undo_results(error.results)
        pp.error(str(error))
        raise cappa.Exit(code=1) from None

    raise cappa.Exit(code=_report_undo_results(results))
