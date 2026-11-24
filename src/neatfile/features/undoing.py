"""Revert the newest run recorded in the undo journal."""

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path

from neatfile.utils.paths import is_case_only_rename, path_exists

from .committing import move_file
from .journal import JournalEntry, JournalWriteError, write_journal


class UndoOutcome(StrEnum):
    """What happened, or would happen, to one journal entry during undo."""

    RESTORED = "restored"
    ORIGINAL_NAME_TAKEN = "original name taken"
    FOLDER_MISSING = "folder missing"
    NOT_FOUND = "not found"

    @property
    def removes_entry(self) -> bool:
        """Report whether the entry no longer describes anything undo can act on, so it leaves the journal."""
        return self in {UndoOutcome.RESTORED, UndoOutcome.NOT_FOUND}


@dataclass(frozen=True)
class UndoResult:
    """The outcome of undoing one journal entry.

    `backup_restored` is True when the file the run replaced was returned from its backup.
    """

    entry: JournalEntry
    outcome: UndoOutcome
    backup_restored: bool = False


class UndoError(Exception):
    """Raise when a file, its backup, or the journal cannot be checked or updated, so undo stops before touching more files.

    `results` holds the entries handled before the failure, so the caller can report them.
    """

    def __init__(self, message: str, *, entry: JournalEntry) -> None:
        super().__init__(message)
        self.entry = entry
        self.results: tuple[UndoResult, ...] = ()


@contextmanager
def _undo_step(
    entry: JournalEntry,
    failure: str,
    *,
    errors: tuple[type[Exception], ...] = (OSError,),
    suffix: str = "",
) -> Generator[None]:
    """Turn a failed filesystem step into an `UndoError` naming what failed and why.

    Args:
        entry: The journal entry the step works on.
        failure: What could not be done, naming the paths involved.
        errors: The exception types that mean the step failed.
        suffix: Text appended after the cause.

    Raises:
        UndoError: If the step raises one of `errors`.
    """
    try:
        yield
    except errors as error:
        msg = f"{failure}: {error}{suffix}"
        raise UndoError(msg, entry=entry) from error


def newest_run(entries: Sequence[JournalEntry]) -> tuple[JournalEntry, ...]:
    """Select the entries of the most recent run, which is the one undo reverts next.

    Args:
        entries: Journal entries in file order.

    Returns:
        tuple[JournalEntry, ...]: Entries sharing the last entry's run ID, in file order. Empty when
            `entries` is empty.
    """
    if not entries:
        return ()
    run_id = entries[-1].run_id
    return tuple(entry for entry in entries if entry.run_id == run_id)


@dataclass
class _DiskState:
    """The real disk plus the moves a preview has already predicted, so each prediction sees the earlier ones.

    With no predicted moves it reports the real disk.
    """

    vacated: set[Path] = field(default_factory=set)
    occupied: set[Path] = field(default_factory=set)

    def exists(self, path: Path) -> bool:
        """Report whether `path` exists once the predicted moves are applied.

        Raises:
            OSError: If `path` cannot be checked on disk.
        """
        if path in self.occupied or any(path in occupied.parents for occupied in self.occupied):
            return True
        if path in self.vacated:
            return False
        return path_exists(path)

    def is_case_only_rename(self, source: Path, destination: Path) -> bool:
        """Report whether `source` exists only as a case-insensitive alias of `destination`.

        Raises:
            OSError: If either path cannot be checked on disk.
        """
        if {source, destination} & (self.vacated | self.occupied):
            return False
        return is_case_only_rename(source=source, destination=destination)

    def move(self, *, source: Path, destination: Path) -> None:
        """Record a predicted move so later predictions see `source` free and `destination` taken."""
        self.occupied.discard(source)
        self.vacated.add(source)
        self.vacated.discard(destination)
        self.occupied.add(destination)


def _predict_outcome(entry: JournalEntry, *, disk: _DiskState) -> UndoOutcome:
    """Decide what undo would do with one entry without moving anything.

    Raises:
        UndoError: If a path of the entry cannot be checked, such as a folder without permission.
    """
    with _undo_step(
        entry=entry,
        failure=f"Cannot check whether {entry.destination} can be moved back to {entry.source}",
    ):
        if not disk.exists(entry.destination):
            if disk.exists(entry.destination.parent):
                return UndoOutcome.NOT_FOUND
            # The folder may be on a drive that is not connected; keep the entry for a later undo
            return UndoOutcome.FOLDER_MISSING
        if disk.exists(entry.source) and not disk.is_case_only_rename(
            source=entry.source, destination=entry.destination
        ):
            return UndoOutcome.ORIGINAL_NAME_TAKEN
    return UndoOutcome.RESTORED


def _backup_would_return(entry: JournalEntry, *, outcome: UndoOutcome, disk: _DiskState) -> bool:
    """Report whether undo would return the file the run replaced from its backup.

    Raises:
        UndoError: If the backup cannot be checked.
    """
    if entry.backup is None or not outcome.removes_entry:
        return False
    with _undo_step(
        entry=entry, failure=f"Cannot check whether backup {entry.backup} still exists"
    ):
        return disk.exists(entry.backup)


def preview_newest_run(entries: Sequence[JournalEntry]) -> tuple[UndoResult, ...]:
    """Predict what undo would do with each entry of the newest run without moving anything, for dry runs.

    Entries are predicted in the order undo handles them, and each prediction sees the moves
    predicted before it, so a name freed and reused within the run predicts the real outcome.

    Args:
        entries: Every readable journal entry, in file order.

    Returns:
        tuple[UndoResult, ...]: One predicted result per entry of the newest run, in the order undo
            would handle them.

    Raises:
        UndoError: If a path cannot be checked. Its `results` lists the entries predicted before
            the failure.
    """
    disk = _DiskState()
    results: list[UndoResult] = []
    try:
        for entry in reversed(newest_run(entries)):
            outcome = _predict_outcome(entry=entry, disk=disk)
            if outcome == UndoOutcome.RESTORED:
                disk.move(source=entry.destination, destination=entry.source)
            backup_returns = _backup_would_return(entry=entry, outcome=outcome, disk=disk)
            if backup_returns and entry.backup is not None:
                disk.move(source=entry.backup, destination=entry.destination)
            results.append(UndoResult(entry=entry, outcome=outcome, backup_restored=backup_returns))
    except UndoError as error:
        error.results = tuple(results)
        raise
    return tuple(results)


def _restore_file(entry: JournalEntry) -> None:
    """Move the file back to its original path, recreating the original folder if needed."""
    with _undo_step(
        entry=entry,
        failure=f"Cannot move {entry.destination} back to {entry.source}",
        errors=(OSError, ValueError),
    ):
        entry.source.parent.mkdir(parents=True, exist_ok=True)
        move_file(source=entry.destination, destination=entry.source, keep_backup=False)


def _restore_backup(entry: JournalEntry) -> bool:
    """Return the file the run replaced from its backup, if the backup still exists.

    Never overwrites: the backup stays in place when something already has the destination path.
    """
    if entry.backup is None:
        return False
    failure = f"Cannot restore backup {entry.backup} to {entry.destination}"
    with _undo_step(entry=entry, failure=failure, suffix=". The backup was left in place"):
        if not path_exists(entry.backup):
            return False
        destination_taken = path_exists(entry.destination)
    if destination_taken:
        msg = f"{failure}: {entry.destination} already exists. The backup was left in place"
        raise UndoError(msg, entry=entry)
    with _undo_step(entry=entry, failure=failure, errors=(OSError, ValueError)):
        move_file(source=entry.backup, destination=entry.destination, keep_backup=False)
    return True


def _remove_from_journal(
    entry: JournalEntry,
    *,
    index: int,
    outcome: UndoOutcome,
    path: Path,
    remaining: list[JournalEntry],
) -> None:
    """Rewrite the journal without the entry at `index`, naming a restored file in the error if the write fails."""
    del remaining[index]
    try:
        write_journal(path=path, entries=remaining)
    except JournalWriteError as error:
        if outcome != UndoOutcome.RESTORED:
            raise UndoError(str(error), entry=entry) from error
        msg = f"Moved {entry.destination} back to {entry.source}. {error}. Its entry stays in the journal"
        if entry.backup is not None:
            msg += f", and the backup {entry.backup} was not returned to {entry.destination}"
        raise UndoError(msg, entry=entry) from error


def _undo_entry(
    *, index: int, path: Path, remaining: list[JournalEntry], results: list[UndoResult]
) -> None:
    """Revert the entry at `index`, then return the file it replaced, so undo can stop after any step.

    The entry's result joins `results` once its file is moved back or its journal line is removed,
    so a failure in a later step still reports it.

    The journal is rewritten before the backup returns. Otherwise a failed rewrite would leave an
    entry whose destination holds the backup, and the next undo would move that file instead.

    Raises:
        UndoError: If a step fails.
    """
    entry = remaining[index]
    outcome = _predict_outcome(entry=entry, disk=_DiskState())
    result = UndoResult(entry=entry, outcome=outcome)
    if outcome == UndoOutcome.RESTORED:
        _restore_file(entry)
        results.append(result)
    if not outcome.removes_entry:
        results.append(result)
        return
    _remove_from_journal(entry, index=index, outcome=outcome, path=path, remaining=remaining)
    if outcome != UndoOutcome.RESTORED:
        results.append(result)
    if _restore_backup(entry):
        results[-1] = replace(result, backup_restored=True)


def undo_newest_run(entries: Sequence[JournalEntry], *, path: Path) -> tuple[UndoResult, ...]:
    """Revert the newest run in the journal so a bad batch of renames and moves can be reversed.

    Entries are reverted in reverse commit order so a name freed and reused within the run unwinds
    correctly. After each entry that is restored or whose file is gone, the journal is rewritten
    without it, so an interrupted undo leaves the journal matching the files on disk, and the file
    the entry replaced returns from its backup. Entries that cannot be restored stay for a later
    undo.

    Every rewrite drops damaged journal lines, so warn the user about them before calling this.

    Args:
        entries: Every readable journal entry, in file order, as read from `path`.
        path: Journal file to rewrite.

    Returns:
        tuple[UndoResult, ...]: One result per entry of the run, in the order they were processed.

    Raises:
        UndoError: If a path cannot be checked or a file cannot be moved back, which keeps its
            entry, its backup cannot be returned, which removes the entry, or the journal cannot be
            rewritten. Its `results` lists the entries handled before the failure, and the failing
            entry too when its file was already moved back or its line removed.
    """
    remaining = list(entries)
    if not remaining:
        return ()
    run_id = remaining[-1].run_id
    run_indexes = [index for index, entry in enumerate(remaining) if entry.run_id == run_id]
    results: list[UndoResult] = []
    try:
        # Deleting from the end keeps the indexes of earlier entries valid
        for index in reversed(run_indexes):
            _undo_entry(index=index, path=path, remaining=remaining, results=results)
    except UndoError as error:
        error.results = tuple(results)
        raise
    return tuple(results)
