"""Read and write the undo journal, a JSON Lines file recording each committed file operation."""

import fcntl
import json
import os
import secrets
import tempfile
from collections.abc import Generator, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import IO, Self

from neatfile import constants

JOURNAL_FILENAME = "undo-journal.jsonl"
_JOURNAL_FILE_MODE = 0o600
_DECODING_REPLACEMENT_CHARACTER = "\ufffd"


def journal_path() -> Path:
    """Locate the undo journal so every caller reads and writes the same file.

    Read the state folder at call time so tests can redirect it.

    Returns:
        Path: Journal file inside the state folder.
    """
    return constants.STATE_DIR / JOURNAL_FILENAME


def new_run_id(now: datetime) -> str:
    """Create an identifier that groups the entries of one neatfile run.

    Args:
        now: Start time of the run.

    Returns:
        str: Timestamp plus six random hex characters, such as `20261124T104207-a1b2c3`.
    """
    return f"{now:%Y%m%dT%H%M%S}-{secrets.token_hex(3)}"


class JournalError(Exception):
    """Base for undo journal failures, naming the journal and the operating system error."""

    _action = "use"

    def __init__(self, path: Path, error: OSError) -> None:
        super().__init__(f"Cannot {self._action} undo journal {path}: {error}")
        self.path = path
        self.os_error = error


class JournalWriteError(JournalError):
    """Raise when the journal cannot be created, appended to, or rewritten."""

    _action = "write"


class JournalReadError(JournalError):
    """Raise when the journal exists but cannot be read."""

    _action = "read"


def journal_lock_path(path: Path) -> Path:
    """Locate the lock file that guards a journal, so every process locks the same file.

    Args:
        path: Journal file.

    Returns:
        Path: Lock file beside the journal.
    """
    return path.with_name(f"{path.name}.lock")


@contextmanager
def journal_lock(path: Path) -> Generator[None]:
    """Hold an exclusive lock on the journal so concurrent neatfile processes never drop each other's entries.

    Take it around every append to the journal and every read that rewrites it. The lock is a
    separate file because a rewrite replaces the journal, and a lock on the replaced file would
    protect nothing.

    Args:
        path: Journal file.

    Raises:
        JournalWriteError: If the lock file cannot be created or locked.
    """
    lock_path = journal_lock_path(path)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = lock_path.open("a", encoding="utf-8")
    except OSError as error:
        raise JournalWriteError(path=path, error=error) from error
    with lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except OSError as error:
            raise JournalWriteError(path=path, error=error) from error
        yield


def _required_text(data: dict[str, object], key: str) -> str:
    """Return a journal field that must be a non-empty string.

    Raises:
        ValueError: If the field is missing, not a string, or empty.
    """
    value = data.get(key)
    if not isinstance(value, str) or not value:
        msg = f"Journal field {key!r} must be a non-empty string, got {value!r}"
        raise ValueError(msg)
    return value


def _required_path(data: dict[str, object], key: str) -> Path:
    """Return a journal field that must be an absolute path.

    Raises:
        ValueError: If the field is missing, not a string, or not an absolute path.
    """
    text = _required_text(data=data, key=key)
    path = Path(text)
    if not path.is_absolute():
        msg = f"Journal field {key!r} must be an absolute path, got {text!r}"
        raise ValueError(msg)
    return path


def _nullable_path(data: dict[str, object], key: str) -> Path | None:
    """Return a journal field that is null or an absolute path."""
    return None if data.get(key) is None else _required_path(data=data, key=key)


def _required_timestamp(data: dict[str, object], key: str) -> datetime:
    """Return a journal field that must be an ISO 8601 timestamp with a UTC offset.

    Raises:
        ValueError: If the field is not a timestamp or has no UTC offset.
    """
    text = _required_text(data=data, key=key)
    try:
        timestamp = datetime.fromisoformat(text)
    except ValueError as error:
        msg = f"Journal field {key!r} must be an ISO 8601 timestamp, got {text!r}"
        raise ValueError(msg) from error
    if timestamp.tzinfo is None:
        msg = f"Journal field {key!r} must include a UTC offset, got {text!r}"
        raise ValueError(msg)
    return timestamp


@dataclass(frozen=True)
class JournalEntry:
    """One committed file operation, enough to reverse it later."""

    run_id: str
    committed_at: datetime
    source: Path
    destination: Path
    backup: Path | None

    def to_json_line(self) -> str:
        """Serialize the entry so it can be appended to the journal.

        Returns:
            str: One JSON object with no trailing newline.
        """
        return json.dumps(
            {
                "run": self.run_id,
                "time": self.committed_at.isoformat(),
                "from": str(self.source),
                "to": str(self.destination),
                "backup": None if self.backup is None else str(self.backup),
            }
        )

    @classmethod
    def from_json_line(cls, line: str) -> "JournalEntry":
        """Parse one journal line so undo can act on it.

        Unknown keys are ignored so newer or hand-edited lines stay readable.

        Args:
            line: One line of the journal.

        Returns:
            JournalEntry: The parsed entry.

        Raises:
            ValueError: If the line is not a JSON object or a field is missing or malformed.
        """
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            msg = f"Journal line is not valid JSON ({error}): {line!r}"
            raise ValueError(msg) from error
        if not isinstance(data, dict):
            msg = f"Journal line must be a JSON object, got {type(data).__name__}: {line!r}"
            raise ValueError(msg)  # noqa: TRY004

        return cls(
            run_id=_required_text(data=data, key="run"),
            committed_at=_required_timestamp(data=data, key="time"),
            source=_required_path(data=data, key="from"),
            destination=_required_path(data=data, key="to"),
            backup=_nullable_path(data=data, key="backup"),
        )


@dataclass(frozen=True)
class JournalContents:
    """Parsed journal: the readable entries and the 1-based numbers of unreadable lines."""

    entries: tuple[JournalEntry, ...]
    damaged_line_numbers: tuple[int, ...]


def read_journal(path: Path) -> JournalContents:
    """Load the journal so callers can undo or trim it, tolerating damaged lines.

    A missing file and an empty file both give empty contents. Blank lines are skipped. Bytes that
    are not valid UTF-8 damage only the line they appear in, even when the line still parses.

    Args:
        path: Journal file.

    Returns:
        JournalContents: Parsed entries and the numbers of lines that could not be parsed.

    Raises:
        JournalReadError: If the file exists but cannot be read.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return JournalContents(entries=(), damaged_line_numbers=())
    except OSError as error:
        raise JournalReadError(path=path, error=error) from error

    entries: list[JournalEntry] = []
    damaged: list[int] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        # `to_json_line` escapes every non-ASCII character, so a literal replacement character
        # means decoding replaced invalid bytes, and a path parsed from the line would be wrong
        if _DECODING_REPLACEMENT_CHARACTER in line:
            damaged.append(line_number)
            continue
        try:
            entries.append(JournalEntry.from_json_line(line))
        except ValueError:
            damaged.append(line_number)
    return JournalContents(entries=tuple(entries), damaged_line_numbers=tuple(damaged))


def write_journal(path: Path, entries: Sequence[JournalEntry]) -> None:
    """Replace the journal atomically so a crash never leaves a half-written file.

    Write a temporary file in the journal's folder, then rename it over the journal. An empty
    `entries` writes an empty file; it does not delete the journal.

    Args:
        path: Journal file.
        entries: Entries to keep, in order.

    Raises:
        JournalWriteError: If the folder or file cannot be written.
    """
    temp_name: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as temp_file:
            temp_name = temp_file.name
            temp_file.writelines(f"{entry.to_json_line()}\n" for entry in entries)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        Path(temp_name).replace(path)
    except OSError as error:
        journal_error = JournalWriteError(path=path, error=error)
        if temp_name is not None:
            try:
                Path(temp_name).unlink()
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                journal_error.add_note(
                    f"Orphaned temporary file {temp_name} could not be removed: {cleanup_error}"
                )
        raise journal_error from error


class RunRecorder:
    """Append the entries of one run to the journal, durably, one file at a time."""

    def __init__(self, *, path: Path, run_id: str) -> None:
        self._path = path
        self._run_id = run_id
        self._file: IO[str] | None = None
        self._lock: ExitStack | None = None

    def prepare(self) -> None:
        """Lock the journal and open it for append before any file is moved.

        Hold the journal lock until `close`, so no other neatfile process rewrites the journal
        while this run appends to it. Create the file readable only by the owner, since it lists
        private paths. Start a new line first when an earlier crash left the last line
        unterminated. Calling it again reopens the file.

        Raises:
            JournalWriteError: If the journal cannot be locked, created, or opened.
        """
        self.close()
        lock = ExitStack()
        lock.enter_context(journal_lock(self._path))
        journal_file: IO[str] | None = None
        try:
            self._path.touch(mode=_JOURNAL_FILE_MODE, exist_ok=True)
            journal_file = self._path.open("a", encoding="utf-8")
            if self._ends_mid_line():
                journal_file.write("\n")
                journal_file.flush()
        except OSError as error:
            journal_error = JournalWriteError(path=self._path, error=error)
            try:
                if journal_file is not None:
                    journal_file.close()
            except OSError as cleanup_error:
                journal_error.add_note(f"Cannot close {self._path}: {cleanup_error}")
            lock.close()
            raise journal_error from error
        self._file = journal_file
        self._lock = lock

    def _ends_mid_line(self) -> bool:
        """Report whether the file has content that does not end in a newline."""
        with self._path.open("rb") as existing:
            existing.seek(0, os.SEEK_END)
            if existing.tell() == 0:
                return False
            existing.seek(-1, os.SEEK_END)
            return existing.read(1) != b"\n"

    def record(self, *, source: Path, destination: Path, backup: Path | None) -> None:
        """Append one committed operation and force it to disk so a crash cannot lose it.

        Args:
            source: Original location of the file.
            destination: Where the file now lives.
            backup: Copy of an overwritten file, if any.

        Raises:
            JournalWriteError: If the line cannot be written.
        """
        if self._file is None:
            self.prepare()
        entry = JournalEntry(
            run_id=self._run_id,
            committed_at=datetime.now().astimezone(),
            source=source,
            destination=destination,
            backup=backup,
        )
        try:
            assert self._file is not None  # noqa: S101
            self._file.write(f"{entry.to_json_line()}\n")
            self._file.flush()
            os.fsync(self._file.fileno())
        except OSError as error:
            raise JournalWriteError(path=self._path, error=error) from error

    def close(self) -> None:
        """Close the journal file and release the lock, removing the file when empty so a run that recorded nothing leaves no journal.

        Safe to call more than once.

        Raises:
            JournalWriteError: If buffered data cannot be flushed or the empty file cannot be removed.
        """
        journal_file, self._file = self._file, None
        lock, self._lock = self._lock, None
        if journal_file is None:
            return
        try:
            journal_file.close()
            if self._path.stat().st_size == 0:
                self._path.unlink()
        except FileNotFoundError:
            return
        except OSError as error:
            raise JournalWriteError(path=self._path, error=error) from error
        finally:
            if lock is not None:
                lock.close()

    def __enter__(self) -> Self:
        """Open the journal for the run."""
        self.prepare()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the journal when the run ends, never hiding an error that ended the run.

        Raises:
            JournalWriteError: If the journal cannot be closed and the run ended without an error.
        """
        try:
            self.close()
        except JournalWriteError as close_error:
            if exc_value is None:
                raise
            exc_value.add_note(str(close_error))


def trim_journal(path: Path, *, max_runs: int) -> tuple[int, ...]:
    """Cap the journal at the newest runs so it cannot grow without bound.

    Runs are ranked by their last appearance in the file. With `max_runs` of 0 the file is
    deleted. Otherwise the file is rewritten only when entries or damaged lines are dropped.

    Args:
        path: Journal file.
        max_runs: Number of newest runs to keep.

    Returns:
        tuple[int, ...]: 1-based numbers of damaged lines that were dropped, so the caller can warn.

    Raises:
        JournalReadError: If the journal exists but cannot be read.
        JournalWriteError: If the journal cannot be rewritten or deleted.
    """
    if max_runs == 0:
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            raise JournalWriteError(path=path, error=error) from error
        return ()

    with journal_lock(path):
        contents = read_journal(path)
        last_seen: dict[str, int] = {}
        for position, entry in enumerate(contents.entries):
            last_seen[entry.run_id] = position
        kept_runs = set(sorted(last_seen, key=lambda run: last_seen[run])[-max_runs:])
        kept = [entry for entry in contents.entries if entry.run_id in kept_runs]

        if len(kept) != len(contents.entries) or contents.damaged_line_numbers:
            write_journal(path=path, entries=kept)
    return contents.damaged_line_numbers
