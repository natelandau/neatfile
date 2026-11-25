"""Feature module."""

from .cleaning import CleanedName, clean_name, parse_date_option
from .committing import CommittedChange, commit_changes, with_backup_location
from .file_dates import fallback_file_date
from .identify_files import find_processable_files
from .journal import (
    JournalEntry,
    JournalReadError,
    JournalWriteError,
    RunRecorder,
    journal_lock,
    journal_path,
    new_run_id,
    read_journal,
    trim_journal,
)
from .sorting import sort_file
from .undoing import (
    UndoError,
    UndoOutcome,
    UndoResult,
    newest_run,
    preview_newest_run,
    undo_newest_run,
)

__all__ = [
    "CleanedName",
    "CommittedChange",
    "JournalEntry",
    "JournalReadError",
    "JournalWriteError",
    "RunRecorder",
    "UndoError",
    "UndoOutcome",
    "UndoResult",
    "clean_name",
    "commit_changes",
    "fallback_file_date",
    "find_processable_files",
    "journal_lock",
    "journal_path",
    "new_run_id",
    "newest_run",
    "parse_date_option",
    "preview_newest_run",
    "read_journal",
    "sort_file",
    "trim_journal",
    "undo_newest_run",
    "with_backup_location",
]
