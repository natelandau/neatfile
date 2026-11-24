"""Tests for reverting the newest run in the undo journal."""

import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from neatfile.features import committing, undoing
from neatfile.features.journal import (
    JournalEntry,
    JournalWriteError,
    read_journal,
    write_journal,
)
from neatfile.features.undoing import (
    UndoError,
    UndoOutcome,
    UndoResult,
    newest_run,
    preview_newest_run,
    undo_newest_run,
)


def _entry(
    source: Path, destination: Path, *, run_id: str = "run-new", backup: Path | None = None
) -> JournalEntry:
    return JournalEntry(
        run_id=run_id,
        committed_at=datetime.now().astimezone(),
        source=source,
        destination=destination,
        backup=backup,
    )


def _undo(journal: Path) -> tuple[UndoResult, ...]:
    return undo_newest_run(read_journal(journal).entries, path=journal)


@pytest.fixture
def journal(tmp_path: Path) -> Path:
    """Locate a journal file inside the test folder."""
    return tmp_path / "state" / "undo-journal.jsonl"


def _setup_restored(tmp_path: Path) -> JournalEntry:
    destination = tmp_path / "sorted" / "b.txt"
    destination.parent.mkdir()
    destination.write_text("moved")
    return _entry(tmp_path / "a.txt", destination)


def _setup_original_folder_deleted(tmp_path: Path) -> JournalEntry:
    (tmp_path / "b.txt").write_text("moved")
    return _entry(tmp_path / "gone" / "deeper" / "a.txt", tmp_path / "b.txt")


def _setup_case_only_rename(tmp_path: Path) -> JournalEntry:
    (tmp_path / "Report.pdf").write_text("report")
    return _entry(tmp_path / "Report.PDF", tmp_path / "Report.pdf")


def _setup_original_name_taken(tmp_path: Path) -> JournalEntry:
    (tmp_path / "a.txt").write_text("newcomer")
    (tmp_path / "b.txt").write_text("moved")
    return _entry(tmp_path / "a.txt", tmp_path / "b.txt")


def _setup_hard_linked_names(tmp_path: Path) -> JournalEntry:
    (tmp_path / "b.txt").write_text("moved")
    (tmp_path / "a.txt").hardlink_to(tmp_path / "b.txt")
    return _entry(tmp_path / "a.txt", tmp_path / "b.txt")


def _setup_folder_missing(tmp_path: Path) -> JournalEntry:
    return _entry(tmp_path / "a.txt", tmp_path / "unplugged" / "b.txt")


def _setup_not_found(tmp_path: Path) -> JournalEntry:
    return _entry(tmp_path / "a.txt", tmp_path / "b.txt")


def _setup_not_found_with_backup(tmp_path: Path) -> JournalEntry:
    backup = tmp_path / "b.txt.bak"
    backup.write_text("replaced")
    return _entry(tmp_path / "a.txt", tmp_path / "b.txt", backup=backup)


@pytest.mark.parametrize(
    ("setup", "outcome", "expected_files", "line_removed", "backup_restored"),
    [
        pytest.param(
            _setup_restored, UndoOutcome.RESTORED, {"a.txt": "moved"}, True, False, id="restored"
        ),
        pytest.param(
            _setup_original_folder_deleted,
            UndoOutcome.RESTORED,
            {"gone/deeper/a.txt": "moved"},
            True,
            False,
            id="original-folder-recreated",
        ),
        pytest.param(
            _setup_case_only_rename,
            UndoOutcome.RESTORED,
            {"Report.PDF": "report"},
            True,
            False,
            id="case-only-rename",
        ),
        pytest.param(
            _setup_original_name_taken,
            UndoOutcome.ORIGINAL_NAME_TAKEN,
            {"a.txt": "newcomer", "b.txt": "moved"},
            False,
            False,
            id="original-name-taken",
        ),
        pytest.param(
            _setup_hard_linked_names,
            UndoOutcome.ORIGINAL_NAME_TAKEN,
            {"a.txt": "moved", "b.txt": "moved"},
            False,
            False,
            id="hard-linked-names",
        ),
        pytest.param(
            _setup_folder_missing,
            UndoOutcome.FOLDER_MISSING,
            {},
            False,
            False,
            id="folder-missing",
        ),
        pytest.param(_setup_not_found, UndoOutcome.NOT_FOUND, {}, True, False, id="not-found"),
        pytest.param(
            _setup_not_found_with_backup,
            UndoOutcome.NOT_FOUND,
            {"b.txt": "replaced"},
            True,
            True,
            id="not-found-with-backup",
        ),
    ],
)
def test_undo_outcomes(
    tmp_path: Path,
    journal: Path,
    setup: Callable[[Path], JournalEntry],
    outcome: UndoOutcome,
    expected_files: dict[str, str],
    line_removed: bool,
    backup_restored: bool,
) -> None:
    """Verify each check gives its outcome, moves only restorable files, and keeps blocked lines."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    entry = setup(workspace)
    write_journal(journal, [entry])

    expected = (UndoResult(entry=entry, outcome=outcome, backup_restored=backup_restored),)
    assert preview_newest_run([entry]) == expected
    results = _undo(journal)

    assert results == expected
    files = {
        path.relative_to(workspace).as_posix(): path.read_text()
        for path in workspace.rglob("*")
        if path.is_file()
    }
    assert files == expected_files
    assert read_journal(journal).entries == (() if line_removed else (entry,))


def test_undo_restores_the_replaced_file_from_its_backup(tmp_path: Path, journal: Path) -> None:
    """Verify the file a run overwrote comes back from its backup."""
    destination = tmp_path / "b.txt"
    destination.write_text("moved")
    backup = tmp_path / "b.txt.bak"
    backup.write_text("replaced")
    source = tmp_path / "a.txt"
    write_journal(journal, [_entry(source, destination, backup=backup)])

    results = _undo(journal)

    assert [result.backup_restored for result in results] == [True]
    assert source.read_text() == "moved"
    assert destination.read_text() == "replaced"
    assert not backup.exists()


def test_undo_reverses_in_reverse_order(tmp_path: Path, journal: Path) -> None:
    """Verify a name freed and reused within one run is unwound, and previewed, correctly."""
    a, b, c = tmp_path / "a.txt", tmp_path / "b.txt", tmp_path / "c.txt"
    b.write_text("original a")
    a.write_text("original c")
    entries = [_entry(a, b), _entry(c, a)]
    write_journal(journal, entries)

    predicted = preview_newest_run(entries)
    results = _undo(journal)

    assert predicted == results
    assert {result.outcome for result in results} == {UndoOutcome.RESTORED}
    assert a.read_text() == "original a"
    assert c.read_text() == "original c"
    assert not b.exists()


def test_undo_touches_only_the_newest_run(tmp_path: Path, journal: Path) -> None:
    """Verify older runs keep their lines and files."""
    old_destination = tmp_path / "old-moved.txt"
    old_destination.write_text("old")
    new_destination = tmp_path / "new-moved.txt"
    new_destination.write_text("new")
    old_entry = _entry(tmp_path / "old.txt", old_destination, run_id="run-old")
    new_entry = _entry(tmp_path / "new.txt", new_destination)
    write_journal(journal, [old_entry, new_entry])

    _undo(journal)

    assert read_journal(journal).entries == (old_entry,)
    assert old_destination.read_text() == "old"
    assert (tmp_path / "new.txt").read_text() == "new"


def test_undo_rewrites_the_journal_after_each_file(
    tmp_path: Path, journal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify an interrupted undo leaves a journal that matches the files on disk."""
    first = _entry(tmp_path / "a.txt", tmp_path / "b.txt")
    second = _entry(tmp_path / "c.txt", tmp_path / "d.txt")
    (tmp_path / "b.txt").write_text("b")
    (tmp_path / "d.txt").write_text("d")
    write_journal(journal, [first, second])
    calls = 0

    def _interrupt_on_second_call(source: Path, destination: Path, *, keep_backup: bool) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        committing.move_file(source=source, destination=destination, keep_backup=keep_backup)

    monkeypatch.setattr(undoing, "move_file", _interrupt_on_second_call)

    with pytest.raises(KeyboardInterrupt):
        _undo(journal)

    assert read_journal(journal).entries == (first,)
    assert (tmp_path / "c.txt").read_text() == "d"


def test_undo_stops_with_an_error_when_a_move_fails(
    tmp_path: Path, journal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a failed move stops the undo, names both paths, and keeps unrestored lines."""
    first = _entry(tmp_path / "a.txt", tmp_path / "b.txt")
    second = _entry(tmp_path / "c.txt", tmp_path / "d.txt")
    (tmp_path / "b.txt").write_text("b")
    (tmp_path / "d.txt").write_text("d")
    write_journal(journal, [first, second])
    calls = 0

    def _fail_on_second_call(source: Path, destination: Path, *, keep_backup: bool) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            msg = "disk full"
            raise OSError(msg)
        committing.move_file(source=source, destination=destination, keep_backup=keep_backup)

    monkeypatch.setattr(undoing, "move_file", _fail_on_second_call)

    with pytest.raises(UndoError) as error_info:
        _undo(journal)

    message = str(error_info.value)
    assert str(first.source) in message
    assert str(first.destination) in message
    assert "disk full" in message
    assert read_journal(journal).entries == (first,)
    assert (tmp_path / "b.txt").read_text() == "b"


def _fail_backup_move(source: Path, destination: Path, *, keep_backup: bool) -> None:
    if source.name.endswith(".bak"):
        msg = "backup disk unreadable"
        raise OSError(msg)
    committing.move_file(source=source, destination=destination, keep_backup=keep_backup)


def _occupy_destination_after_move(source: Path, destination: Path, *, keep_backup: bool) -> None:
    committing.move_file(source=source, destination=destination, keep_backup=keep_backup)
    source.write_text("appeared meanwhile")


@pytest.mark.parametrize(
    ("patched_move", "cause"),
    [
        pytest.param(_fail_backup_move, "backup disk unreadable", id="backup-move-fails"),
        pytest.param(_occupy_destination_after_move, "already exists", id="destination-occupied"),
    ],
)
def test_undo_reports_a_backup_that_cannot_return(
    tmp_path: Path,
    journal: Path,
    monkeypatch: pytest.MonkeyPatch,
    patched_move: Callable[..., None],
    cause: str,
) -> None:
    """Verify a restored file leaves the journal and the error names where the backup still is."""
    source, destination, backup = tmp_path / "a.txt", tmp_path / "b.txt", tmp_path / "b.txt.bak"
    destination.write_text("moved")
    backup.write_text("replaced")
    write_journal(journal, [_entry(source, destination, backup=backup)])
    monkeypatch.setattr(undoing, "move_file", patched_move)

    with pytest.raises(UndoError) as error_info:
        _undo(journal)

    message = str(error_info.value)
    assert str(backup) in message
    assert str(destination) in message
    assert cause in message
    assert source.read_text() == "moved"
    assert backup.read_text() == "replaced"
    assert read_journal(journal).entries == ()


def test_newest_run_selects_the_last_run_in_file_order() -> None:
    """Verify only the last run's entries are taken, in file order."""
    old = _entry(Path("/a"), Path("/b"), run_id="run-old")
    new_first = _entry(Path("/c"), Path("/d"))
    new_second = _entry(Path("/e"), Path("/f"))

    assert newest_run([old, new_first, new_second]) == (new_first, new_second)
    assert newest_run([]) == ()


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores folder permissions")
def test_undo_stops_when_a_path_cannot_be_checked(tmp_path: Path, journal: Path) -> None:
    """Verify an unreadable folder stops undo with an error naming the entry, keeping its line."""
    handled = _entry(tmp_path / "c.txt", tmp_path / "gone.txt")
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "b.txt").write_text("moved")
    blocked = _entry(tmp_path / "a.txt", locked / "b.txt")
    write_journal(journal, [blocked, handled])
    locked.chmod(0)
    try:
        with pytest.raises(UndoError) as error_info:
            _undo(journal)
    finally:
        locked.chmod(0o700)

    assert str(blocked.destination) in str(error_info.value)
    assert error_info.value.results == (UndoResult(entry=handled, outcome=UndoOutcome.NOT_FOUND),)
    assert read_journal(journal).entries == (blocked,)
    assert (locked / "b.txt").read_text() == "moved"


def test_undo_reports_a_restored_file_whose_entry_cannot_be_removed(
    tmp_path: Path, journal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a failed journal rewrite after a restore names the restored file and reports it."""
    source, destination = tmp_path / "a.txt", tmp_path / "b.txt"
    destination.write_text("moved")
    entry = _entry(source, destination)
    write_journal(journal, [entry])

    def _fail_write(path: Path, entries: object) -> None:
        raise JournalWriteError(path, OSError("disk full"))

    monkeypatch.setattr(undoing, "write_journal", _fail_write)

    with pytest.raises(UndoError) as error_info:
        _undo(journal)

    message = str(error_info.value)
    assert str(source) in message
    assert str(destination) in message
    assert "disk full" in message
    assert error_info.value.results == (UndoResult(entry=entry, outcome=UndoOutcome.RESTORED),)
    assert source.read_text() == "moved"
