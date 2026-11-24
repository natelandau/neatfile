"""Tests for the undo journal file format."""

import fcntl
import gc
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from neatfile.features.journal import (
    JournalContents,
    JournalEntry,
    JournalReadError,
    JournalWriteError,
    RunRecorder,
    journal_lock,
    journal_lock_path,
    journal_path,
    new_run_id,
    read_journal,
    trim_journal,
    write_journal,
)


def _entry(run_id: str, name: str = "a.txt", backup: Path | None = None) -> JournalEntry:
    return JournalEntry(
        run_id=run_id,
        committed_at=datetime.now().astimezone(),
        source=Path("/src") / name,
        destination=Path("/dst") / name,
        backup=backup,
    )


@pytest.mark.parametrize("has_backup", [False, True])
@pytest.mark.parametrize(
    "name", ["plain.txt", "quote \"and' apostrophe.pdf", "café menü.pdf", "line\nbreak.txt"]
)
def test_entry_round_trips_through_a_json_line(name: str, has_backup: bool) -> None:
    """Verify a path with awkward characters survives the journal line format."""
    entry = _entry("20261124T104207-a1b2c3", name, Path("/bak") / name if has_backup else None)

    line = entry.to_json_line()

    assert "\n" not in line
    assert set(json.loads(line)) == {"run", "time", "from", "to", "backup"}
    assert JournalEntry.from_json_line(line) == entry


def test_read_journal_reports_damaged_lines(tmp_path: Path) -> None:
    """Verify damaged lines are numbered, blanks are skipped, and unknown keys are tolerated."""
    good = _entry("r1").to_json_line()
    missing_to = json.dumps({"run": "r1", "time": "2026-11-24T10:00:00+00:00", "from": "/a"})
    extra_key = json.dumps({**json.loads(good), "note": "x"})
    path = tmp_path / "journal.jsonl"
    path.write_text(f"{good}\nnot json\n{missing_to}\n\n{extra_key}\n")

    contents = read_journal(path)

    assert len(contents.entries) == 2
    assert contents.damaged_line_numbers == (2, 3)


@pytest.mark.parametrize("write_empty", [False, True], ids=["missing-file", "empty-rewrite"])
def test_read_journal_without_entries_is_empty(tmp_path: Path, write_empty: bool) -> None:
    """Verify a missing journal and an empty rewrite both read as empty."""
    path = tmp_path / "journal.jsonl"
    if write_empty:
        write_journal(path, [])

    assert read_journal(path) == JournalContents(entries=(), damaged_line_numbers=())


def test_recorder_appends_one_line_per_file_and_creates_the_folder() -> None:
    """Verify the recorder creates the state folder and appends entries in order."""
    path = journal_path()
    assert not path.parent.exists()

    with RunRecorder(path=path, run_id="r1") as recorder:
        recorder.record(source=Path("/s/1"), destination=Path("/d/1"), backup=None)
        recorder.record(source=Path("/s/2"), destination=Path("/d/2"), backup=Path("/b/2"))

    entries = read_journal(path).entries
    assert [entry.source for entry in entries] == [Path("/s/1"), Path("/s/2")]
    assert {entry.run_id for entry in entries} == {"r1"}
    assert entries[1].backup == Path("/b/2")


def test_recorder_prepare_fails_when_folder_is_not_writable(tmp_path: Path) -> None:
    """Verify an unwritable journal folder raises an error naming the path."""
    blocker = tmp_path / "blocker"
    blocker.write_text("regular file")
    path = blocker / "undo-journal.jsonl"

    with pytest.raises(JournalWriteError, match="blocker"):
        RunRecorder(path=path, run_id="r1").prepare()


@pytest.mark.parametrize(
    ("lines", "max_runs", "dropped", "kept_runs", "unchanged"),
    [
        pytest.param(["a", "a", "b", "c"], 2, (), ["b", "c"], False, id="drops-oldest-runs"),
        pytest.param(
            ["a", "a", "b", "c"], 5, (), ["a", "a", "b", "c"], True, id="within-limit-untouched"
        ),
        pytest.param(["a"], 0, (), None, False, id="zero-runs-deletes"),
        pytest.param([None, "a"], 1, (1,), ["a"], False, id="drops-damaged-lines"),
    ],
)
def test_trim_journal(
    tmp_path: Path,
    lines: list[str | None],
    max_runs: int,
    dropped: tuple[int, ...],
    kept_runs: list[str] | None,
    unchanged: bool,
) -> None:
    """Verify trimming keeps the newest runs, drops damaged lines, and rewrites only when needed.

    A None line is a damaged line. None for `kept_runs` means the journal is deleted.
    """
    path = tmp_path / "state" / "journal.jsonl"
    path.parent.mkdir()
    path.write_text(
        "".join(f"{'junk' if run is None else _entry(run).to_json_line()}\n" for run in lines)
    )
    before_bytes = path.read_bytes()
    before_inode = path.stat().st_ino

    assert trim_journal(path, max_runs=max_runs) == dropped

    if kept_runs is None:
        assert not path.exists()
        return
    contents = read_journal(path)
    assert [entry.run_id for entry in contents.entries] == kept_runs
    assert contents.damaged_line_numbers == ()
    # An atomic rewrite leaves no temporary file beside the journal and its lock
    assert {child.name for child in path.parent.iterdir()} == {
        path.name,
        journal_lock_path(path).name,
    }
    if unchanged:
        assert path.read_bytes() == before_bytes
        assert path.stat().st_ino == before_inode


def test_new_run_id_format() -> None:
    """Verify the run identifier has a timestamp prefix and a random suffix."""
    run_id = new_run_id(datetime(2026, 11, 24, 10, 42, 7, tzinfo=UTC))

    assert run_id.startswith("20261124T104207-")
    assert len(run_id) == len("20261124T104207-a1b2c3")


def test_recorder_starts_a_new_line_after_a_torn_last_line(tmp_path: Path) -> None:
    """Verify an unterminated last line does not swallow the next entry."""
    path = tmp_path / "journal.jsonl"
    path.write_text(_entry("a").to_json_line() + '\n{"run": "torn')

    with RunRecorder(path=path, run_id="b") as recorder:
        recorder.record(source=Path("/s/1"), destination=Path("/d/1"), backup=None)

    contents = read_journal(path)
    assert [entry.run_id for entry in contents.entries] == ["a", "b"]
    assert contents.damaged_line_numbers == (2,)


def test_recorder_prepare_twice_does_not_duplicate_or_leak(
    tmp_path: Path, recwarn: pytest.WarningsRecorder
) -> None:
    """Verify a second prepare reopens the file without duplicating entries or leaking a handle."""
    path = tmp_path / "journal.jsonl"
    recorder = RunRecorder(path=path, run_id="r1")
    recorder.prepare()
    recorder.prepare()
    recorder.record(source=Path("/s"), destination=Path("/d"), backup=None)
    recorder.close()
    del recorder
    gc.collect()

    assert len(read_journal(path).entries) == 1
    assert not [warning for warning in recwarn if issubclass(warning.category, ResourceWarning)]


def test_recorder_closes_the_file_when_preparing_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recwarn: pytest.WarningsRecorder
) -> None:
    """Verify a failed prepare raises a journal error, leaves no file open, and releases the lock."""
    path = tmp_path / "journal.jsonl"

    def _fail_check(self: RunRecorder) -> bool:
        msg = "read failed"
        raise OSError(msg)

    monkeypatch.setattr(RunRecorder, "_ends_mid_line", _fail_check)

    with pytest.raises(JournalWriteError, match="read failed"):
        RunRecorder(path=path, run_id="r1").prepare()
    gc.collect()

    assert not [warning for warning in recwarn if issubclass(warning.category, ResourceWarning)]
    with journal_lock(path):
        pass


def test_recorder_holds_the_journal_lock_until_closed(tmp_path: Path) -> None:
    """Verify another process cannot lock the journal while a run records to it."""
    path = tmp_path / "journal.jsonl"
    recorder = RunRecorder(path=path, run_id="r1")
    recorder.prepare()

    with journal_lock_path(path).open("a") as other_process_lock:
        with pytest.raises(BlockingIOError):
            fcntl.flock(other_process_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        recorder.close()
        fcntl.flock(other_process_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_recorder_close_failure_does_not_hide_the_run_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the error that ended a run propagates, with the journal close failure as a note."""
    path = tmp_path / "journal.jsonl"
    close_error = JournalWriteError(path, OSError("flush failed"))
    recorder = RunRecorder(path=path, run_id="r1")
    real_close = recorder.close

    run_error = KeyError("run failed")

    def _fail_close() -> None:
        real_close()
        raise close_error

    def _run() -> None:
        with recorder:
            monkeypatch.setattr(recorder, "close", _fail_close)
            raise run_error

    with pytest.raises(KeyError) as error_info:
        _run()

    assert str(close_error) in error_info.value.__notes__


def test_recorder_creates_the_journal_readable_only_by_the_owner(tmp_path: Path) -> None:
    """Verify the journal, which lists private paths, is created with mode 0600."""
    path = tmp_path / "journal.jsonl"

    with RunRecorder(path=path, run_id="r1"):
        assert path.stat().st_mode & 0o777 == 0o600


_ACCENTED_LINE = _entry("a", name="menu-\N{LATIN SMALL LETTER E WITH ACUTE}.txt").to_json_line()


@pytest.mark.parametrize(
    ("payload", "run_ids", "damaged"),
    [
        pytest.param(
            _entry("a").to_json_line().encode()
            + b"\n\xff\xfe\n"
            + _entry("b").to_json_line().encode(),
            ["a", "b"],
            (2,),
            id="bad-bytes-on-their-own-line",
        ),
        pytest.param(
            _ACCENTED_LINE.replace("\\u00e9", "\udcff").encode("utf-8", "surrogateescape") + b"\n",
            [],
            (1,),
            id="bad-byte-inside-a-parseable-line",
        ),
    ],
)
def test_read_journal_confines_invalid_utf8_to_its_line(
    tmp_path: Path, payload: bytes, run_ids: list[str], damaged: tuple[int, ...]
) -> None:
    """Verify a bad byte damages only its own line, even when the line still parses as JSON."""
    path = tmp_path / "journal.jsonl"
    path.write_bytes(payload)

    contents = read_journal(path)

    assert [entry.run_id for entry in contents.entries] == run_ids
    assert contents.damaged_line_numbers == damaged


def test_read_journal_wraps_unreadable_file_errors(tmp_path: Path) -> None:
    """Verify a path that cannot be read as a file raises an error naming the path."""
    path = tmp_path / "journal.jsonl"
    path.mkdir()

    with pytest.raises(JournalReadError, match=re.escape(path.name)):
        read_journal(path)


def test_write_journal_failure_removes_the_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a failed replace raises JournalWriteError and leaves no temp file behind."""
    folder = tmp_path / "journal_folder"
    folder.mkdir()
    path = folder / "journal.jsonl"

    def _fail(self: Path, target: Path) -> Path:
        msg = "replace failed"
        raise OSError(msg)

    monkeypatch.setattr(Path, "replace", _fail)

    with pytest.raises(JournalWriteError, match="replace failed"):
        write_journal(path, [_entry("r1")])

    assert list(folder.iterdir()) == []


_VALID_FIELDS = {"run": "r1", "time": "2026-11-24T10:00:00+00:00", "from": "/a", "to": "/b"}


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"run": None}, "run"),
        ({"time": "yesterday"}, "time"),
        ({"time": "2026-11-24T10:00:00"}, "time"),
        ({"from": "relative/a"}, "from"),
        ({"to": 5}, "to"),
        ({"backup": "relative/b"}, "backup"),
    ],
)
def test_from_json_line_error_names_the_field(overrides: dict[str, object], field: str) -> None:
    """Verify a bad field raises a ValueError naming that field."""
    line = json.dumps({**_VALID_FIELDS, **overrides})

    with pytest.raises(ValueError, match=re.escape(f"'{field}'")):
        JournalEntry.from_json_line(line)
