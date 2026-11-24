"""Test that commands record each committed file in the undo journal."""

from collections.abc import Callable
from pathlib import Path

import cappa
import pytest
from cappa.base import invoke

from neatfile.cli import NeatFile, configure_output
from neatfile.commands import JOURNAL_DAMAGED_LINES_DROPPED_MESSAGE, JOURNAL_WRITE_FAILED_MESSAGE
from neatfile.features import (
    CommittedChange,
    JournalWriteError,
    committing,
    journal_path,
    read_journal,
)
from neatfile.features.committing import BACKUP_LOCATION_MESSAGE, PARTIAL_MOVE_MESSAGE

CLEAN_ARGS = ["--separator", "DASH", "--date-format", ""]


def _run(argv: list[str]) -> int | str | None:
    """Invoke the CLI and return its exit code."""
    with pytest.raises(cappa.Exit) as exit_info:
        invoke(obj=NeatFile, argv=argv, deps=[configure_output])
    return exit_info.value.code


def _without_whitespace(text: str) -> str:
    """Remove all whitespace so assertions survive Rich wrapping long lines.

    Captured output has `tmp_path` stripped by the `capsys_strip_tmp_path` setting.
    """
    return "".join(text.split())


def test_clean_records_each_renamed_file(create_file) -> None:
    """Verify clean records every renamed file under one run ID."""
    # Given: Two files whose names clean to dash-separated names
    first = create_file("foo bar.txt")
    second = create_file("baz qux.txt")

    # When: Cleaning both files in one run
    _run(["clean", str(first), str(second), *CLEAN_ARGS])

    # Then: The journal holds one entry per file, all from the same run
    entries = read_journal(journal_path()).entries
    assert len({entry.run_id for entry in entries}) == 1
    assert {(entry.source, entry.destination, entry.backup) for entry in entries} == {
        (first.absolute(), first.with_name("foo-bar.txt").absolute(), None),
        (second.absolute(), second.with_name("baz-qux.txt").absolute(), None),
    }


def test_journal_paths_have_no_parent_folder_segments(create_file, tmp_path) -> None:
    """Verify the journal records paths without `..`, so undo finds them after a folder they named is gone."""
    # Given: A file named on the command line through a folder and `..`
    file = create_file("foo bar.txt")
    detour = tmp_path / "detour"
    detour.mkdir()

    # When: Cleaning the file, then removing the folder the path passed through
    _run(["clean", str(detour / ".." / file.name), *CLEAN_ARGS])
    detour.rmdir()

    # Then: The entry names the file and its new name directly
    (entry,) = read_journal(journal_path()).entries
    assert entry.source == file
    assert entry.destination == file.with_name("foo-bar.txt")


def test_sort_records_the_move(mock_project) -> None:
    """Verify sort records the move into the project folder."""
    # Given: A file that matches one project folder
    originals, project_path = mock_project
    file = originals / "quick brown fox.txt"

    # When: Sorting the file into the project
    _run(["sort", str(file), "--project", "mock_folder_project"])

    # Then: The entry records the move into the project
    (entry,) = read_journal(journal_path()).entries
    assert entry.source == file.absolute()
    assert entry.destination.is_relative_to(project_path)
    assert entry.destination.exists()


@pytest.mark.parametrize(
    ("file_name", "extra_args", "commits_fail"),
    [
        pytest.param("foo bar.txt", ["--dry-run"], False, id="dry-run"),
        pytest.param("foo-bar.txt", [], False, id="no-changes"),
        pytest.param("foo bar.txt", [], True, id="every-commit-fails"),
    ],
)
def test_runs_that_change_nothing_record_nothing(
    create_file, mocker, isolate_state_dir, file_name, extra_args, commits_fail
) -> None:
    """Verify a run that moves no file leaves no journal behind."""
    # Given: A file, and copies that fail when requested
    file = create_file(file_name)
    if commits_fail:
        mocker.patch(
            "neatfile.features.committing.copy_file", side_effect=ValueError("copy failed")
        )

    # When: Cleaning the file
    _run(["clean", str(file), *CLEAN_ARGS, *extra_args])

    # Then: No journal exists
    assert not journal_path().exists()
    assert file.exists()


def test_replaced_file_backup_is_recorded(create_file) -> None:
    """Verify the backup of an overwritten file is recorded and holds the old content."""
    # Given: A file whose cleaned name is already taken
    file = create_file("foo bar.txt", content="new content")
    create_file("foo-bar.txt", content="old content")

    # When: Cleaning the file
    _run(["clean", str(file), *CLEAN_ARGS])

    # Then: The entry names a backup holding the replaced file's content
    (entry,) = read_journal(journal_path()).entries
    assert entry.backup is not None
    assert entry.backup.read_text() == "old content"
    assert entry.destination.read_text() == "new content"


def test_journal_unwritable_stops_before_changes(
    tmp_path, create_file, isolate_state_dir, capsys
) -> None:
    """Verify an unwritable journal stops the run before any file changes."""
    # Given: The state folder path is a regular file, so the journal cannot be created
    isolate_state_dir.write_text("")
    file = create_file("foo bar.txt")

    # When: Cleaning the file
    code = _run(["clean", str(file), *CLEAN_ARGS])

    # Then: The run fails, names the journal, and leaves the file alone
    captured = capsys.readouterr()
    assert code == 1
    assert _without_whitespace(str(journal_path().relative_to(tmp_path))) in _without_whitespace(
        captured.out + captured.err
    )
    assert file.exists()


@pytest.mark.parametrize("replaces_existing", [False, True], ids=["no-backup", "with-backup"])
def test_journal_append_failure_stops_later_changes(
    tmp_path, create_file, mocker, capsys, replaces_existing
) -> None:
    """Verify a failed journal append stops the run and names every path of the unrecorded file."""
    # Given: Two files, possibly with files at their cleaned names, and a journal that rejects
    # every append
    first = create_file("alpha one.txt")
    second = create_file("beta two.txt")
    if replaces_existing:
        create_file("alpha-one.txt", content="old alpha")
        create_file("beta-two.txt", content="old beta")
    append_error = OSError("disk full")
    unrecorded: list[CommittedChange] = []

    def _fail_record(*, source: Path, destination: Path, backup: Path | None) -> None:
        unrecorded.append(CommittedChange(source=source, destination=destination, backup=backup))
        raise JournalWriteError(journal_path(), append_error)

    mocker.patch("neatfile.commands.RunRecorder.record", side_effect=_fail_record)

    # When: Cleaning both files
    code = _run(["clean", str(first), str(second), *CLEAN_ARGS])

    # Then: The run fails after the first file and names the journal and the moved file
    captured = _without_whitespace("".join(capsys.readouterr()))
    (change,) = unrecorded
    expected = JOURNAL_WRITE_FAILED_MESSAGE.format(
        error=append_error,
        source=change.source.relative_to(tmp_path),
        destination=change.destination.relative_to(tmp_path),
    )
    assert code == 1
    assert _without_whitespace(expected) in captured
    assert _without_whitespace(str(journal_path().relative_to(tmp_path))) in captured
    assert [first.exists(), second.exists()].count(True) == 1
    assert (change.backup is not None) == replaces_existing
    if change.backup is not None:
        backup_location = BACKUP_LOCATION_MESSAGE.format(
            destination=change.destination.relative_to(tmp_path),
            backup=change.backup.relative_to(tmp_path),
        )
        assert _without_whitespace(backup_location) in captured


def test_original_left_behind_is_reported_and_not_recorded(
    tmp_path, create_file, mocker, capsys
) -> None:
    """Verify a move whose original cannot be deleted is reported and kept out of the journal."""
    # Given: A file whose original cannot be deleted after it is copied
    source = create_file("foo bar.txt", content="content")
    destination = source.with_name("foo-bar.txt")
    real_unlink = Path.unlink
    delete_error = PermissionError("permission denied")

    def _fail_for_source(path: Path, *, missing_ok: bool = False) -> None:
        if path == source:
            raise delete_error
        real_unlink(path, missing_ok=missing_ok)

    mocker.patch.object(Path, "unlink", autospec=True, side_effect=_fail_for_source)

    # When: Cleaning the file
    _run(["clean", str(source), *CLEAN_ARGS])

    # Then: Both copies remain, the step is reported, and nothing is recorded
    captured = capsys.readouterr()
    expected = PARTIAL_MOVE_MESSAGE.format(
        source=source.relative_to(tmp_path),
        destination=destination.relative_to(tmp_path),
        error=delete_error,
    )
    assert _without_whitespace(expected) in _without_whitespace(captured.out + captured.err)
    assert source.exists()
    assert destination.read_text() == "content"
    assert not read_journal(journal_path()).entries


def test_interrupted_run_keeps_records_of_finished_files(create_file, mocker) -> None:
    """Verify files moved before an interrupt stay in the journal."""
    # Given: Three files, and a move that is interrupted on the third file
    files = [create_file(name) for name in ("alpha one.txt", "beta two.txt", "gamma three.txt")]
    real_move_file = committing.move_file
    calls: list[Path] = []

    def _interrupt_third(source: Path, destination: Path, *, keep_backup: bool) -> Path | None:
        calls.append(source)
        if len(calls) == 3:
            raise KeyboardInterrupt
        return real_move_file(source=source, destination=destination, keep_backup=keep_backup)

    mocker.patch("neatfile.features.committing.move_file", side_effect=_interrupt_third)

    # When: Cleaning the files and the run is interrupted
    with pytest.raises(KeyboardInterrupt):
        invoke(
            obj=NeatFile,
            argv=["clean", *(str(file) for file in files), *CLEAN_ARGS],
            deps=[configure_output],
        )

    # Then: The journal records the two files that moved
    entries = read_journal(journal_path()).entries
    assert [entry.source for entry in entries] == [path.absolute() for path in calls[:2]]
    assert all(entry.destination.exists() for entry in entries)


def test_trims_to_undo_history_runs(
    create_file, write_user_config: Callable[[dict[str, object]], Path]
) -> None:
    """Verify the journal keeps only the newest `undo_history_runs` runs."""
    # Given: A history limit of two runs
    write_user_config({"undo_history_runs": 2})
    run_ids: list[str] = []

    # When: Three runs each rename one file
    for name in ("alpha one.txt", "beta two.txt", "gamma three.txt"):
        _run(["clean", str(create_file(name)), *CLEAN_ARGS])
        run_ids.append(read_journal(journal_path()).entries[-1].run_id)

    # Then: Only the last two runs remain
    entries = read_journal(journal_path()).entries
    assert [entry.run_id for entry in entries] == run_ids[1:]


def test_zero_history_deletes_journal(
    create_file, write_user_config: Callable[[dict[str, object]], Path]
) -> None:
    """Verify setting `undo_history_runs` to 0 deletes the journal on the next run."""
    # Given: A journal from a run with the default history
    _run(["clean", str(create_file("alpha one.txt")), *CLEAN_ARGS])
    assert journal_path().exists()

    # When: Another run commits a file with the journal turned off
    write_user_config({"undo_history_runs": 0})
    _run(["clean", str(create_file("beta two.txt")), *CLEAN_ARGS])

    # Then: No journal remains
    assert not journal_path().exists()


def test_damaged_lines_dropped_are_reported(tmp_path, create_file, capsys) -> None:
    """Verify a run warns when trimming drops unreadable journal lines."""
    # Given: A journal with an unreadable line
    journal = journal_path()
    journal.parent.mkdir(parents=True)
    journal.write_text("not json\n")

    # When: A run commits a file
    _run(["clean", str(create_file("alpha one.txt")), *CLEAN_ARGS])

    # Then: The damaged line is dropped and reported by number
    captured = capsys.readouterr()
    expected = JOURNAL_DAMAGED_LINES_DROPPED_MESSAGE.format(
        line_numbers="1", path=journal.relative_to(tmp_path)
    )
    assert _without_whitespace(expected) in _without_whitespace(captured.out + captured.err)
    contents = read_journal(journal)
    assert contents.damaged_line_numbers == ()
    assert len(contents.entries) == 1
