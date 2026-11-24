"""Test the undo command."""

import io
import os

import cappa
import pytest
from cappa.base import invoke

from neatfile.cli import NeatFile, configure_output
from neatfile.commands import (
    CHANGES_NOT_APPLIED_MESSAGE,
    CONFIRMATION_NO_INPUT_MESSAGE,
    JOURNAL_CHANGED_MESSAGE,
    JOURNAL_DAMAGED_LINES_IGNORED_MESSAGE,
    NOTHING_TO_UNDO_MESSAGE,
    UNDO_BACKUP_RESTORED_MESSAGE,
    UNDO_BACKUP_WOULD_RETURN_MESSAGE,
    UNDO_OUTCOME_MESSAGES,
)
from neatfile.features import UndoOutcome, journal_path, read_journal, undoing

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


def test_clean_then_undo_restores_names(create_file) -> None:
    """Verify undo gives cleaned files their old names and empties the journal."""
    # Given: Two files cleaned in one run
    first = create_file("foo bar.txt")
    second = create_file("baz qux.txt")
    _run(["clean", str(first), str(second), *CLEAN_ARGS])
    assert not first.exists()

    # When: Undoing the run
    exit_code = _run(["undo", "--force"])

    # Then: Both files have their old names and the journal is empty
    assert exit_code == 0
    assert first.exists()
    assert second.exists()
    assert not first.with_name("foo-bar.txt").exists()
    assert not second.with_name("baz-qux.txt").exists()
    assert read_journal(journal_path()).entries == ()


def test_two_undos_revert_two_runs(create_file) -> None:
    """Verify each undo reverts one run, newest first."""
    # Given: Two clean runs on different files
    older = create_file("foo bar.txt")
    newer = create_file("baz qux.txt")
    _run(["clean", str(older), *CLEAN_ARGS])
    _run(["clean", str(newer), *CLEAN_ARGS])

    # When: Undoing once
    first_exit_code = _run(["undo", "--force"])

    # Then: Only the newer run is reverted
    assert newer.exists()
    assert not older.exists()
    assert older.with_name("foo-bar.txt").exists()

    # When: Undoing again
    second_exit_code = _run(["undo", "--force"])

    # Then: The older run is reverted too
    assert (first_exit_code, second_exit_code) == (0, 0)
    assert older.exists()
    assert read_journal(journal_path()).entries == ()


def test_sort_then_undo_moves_back(mock_project) -> None:
    """Verify undo moves a sorted file back to its original folder."""
    # Given: A file sorted into the project
    originals, _ = mock_project
    file = originals / "quick brown fox.txt"
    _run(["sort", str(file), "--project", "mock_folder_project"])
    assert not file.exists()

    # When: Undoing the sort
    exit_code = _run(["undo", "--force"])

    # Then: The file is back in the originals folder
    assert exit_code == 0
    assert file.exists()


def test_undo_with_empty_journal(capsys) -> None:
    """Verify undo with no journal reports there is nothing to undo."""
    # When: Undoing with no journal
    exit_code = _run(["undo"])

    # Then: The command succeeds and says nothing is to be undone
    assert exit_code == 0
    assert NOTHING_TO_UNDO_MESSAGE in capsys.readouterr().out


def test_undo_dry_run_changes_nothing(create_file) -> None:
    """Verify a dry-run undo leaves the files and the journal alone."""
    # Given: A cleaned file
    file = create_file("foo bar.txt")
    _run(["clean", str(file), *CLEAN_ARGS])
    journal_before = journal_path().read_text()

    # When: Previewing the undo
    exit_code = _run(["undo", "-n"])

    # Then: The file keeps its new name and the journal is unchanged
    assert exit_code == 0
    assert not file.exists()
    assert file.with_name("foo-bar.txt").exists()
    assert journal_path().read_text() == journal_before


@pytest.mark.parametrize(
    ("stdin_text", "expected_code", "expected_message"),
    [
        pytest.param("n\n", 0, CHANGES_NOT_APPLIED_MESSAGE, id="declined"),
        pytest.param("", 1, CONFIRMATION_NO_INPUT_MESSAGE, id="no-input"),
    ],
)
def test_undo_asks_even_without_confirm_changes(
    create_file, monkeypatch, capsys, stdin_text, expected_code, expected_message
) -> None:
    """Verify undo asks before restoring even though the run did not ask for confirmation."""
    # Given: A cleaned file and the given stdin
    file = create_file("foo bar.txt")
    _run(["clean", str(file), *CLEAN_ARGS])
    capsys.readouterr()
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))

    # When: Undoing without --force
    exit_code = _run(["undo"])

    # Then: Nothing is restored and the outcome is reported
    assert exit_code == expected_code
    assert not file.exists()
    captured = capsys.readouterr()
    assert _without_whitespace(expected_message) in _without_whitespace(captured.out + captured.err)


def test_undo_stops_when_another_run_is_recorded_before_confirmation(
    create_file, tmp_path, monkeypatch, capsys
) -> None:
    """Verify undo moves nothing when the journal gains a newer run while undo waits for an answer."""
    # Given: A cleaned file, and a second run that finishes while undo waits for confirmation
    first = create_file("foo bar.txt")
    second = create_file("baz qux.txt")
    _run(["clean", str(first), *CLEAN_ARGS])

    def _clean_another_file_then_accept() -> bool:
        _run(["clean", str(second), *CLEAN_ARGS])
        return True

    monkeypatch.setattr("neatfile.commands._ask_to_apply", _clean_another_file_then_accept)
    capsys.readouterr()

    # When: Undoing and confirming
    exit_code = _run(["undo"])

    # Then: Undo fails, both runs keep their files and journal lines, and the user is told why
    assert exit_code == 1
    assert first.with_name("foo-bar.txt").exists()
    assert second.with_name("baz-qux.txt").exists()
    assert len(read_journal(journal_path()).entries) == 2
    expected = JOURNAL_CHANGED_MESSAGE.format(path=journal_path().relative_to(tmp_path))
    captured = capsys.readouterr()
    assert _without_whitespace(expected) in _without_whitespace(captured.out + captured.err)


def test_undo_exits_1_when_a_file_is_skipped(create_file, tmp_path, capsys) -> None:
    """Verify undo skips a file whose old name is taken, names it, and fails."""
    # Given: A cleaned file, and a new file at its old name
    file = create_file("foo bar.txt", content="original")
    _run(["clean", str(file), *CLEAN_ARGS])
    file.write_text("newcomer")
    capsys.readouterr()

    # When: Undoing the run
    exit_code = _run(["undo", "--force"])

    # Then: The command fails, names the file, and overwrites nothing
    assert exit_code == 1
    assert file.read_text() == "newcomer"
    assert file.with_name("foo-bar.txt").read_text() == "original"
    assert _without_whitespace(str(file.relative_to(tmp_path))) in _without_whitespace(
        capsys.readouterr().out
    )


def test_undo_warns_about_damaged_journal_lines(create_file, tmp_path, capsys) -> None:
    """Verify undo names the journal and the damaged lines it is about to drop."""
    # Given: A cleaned file and a damaged line at the end of the journal
    file = create_file("foo bar.txt")
    _run(["clean", str(file), *CLEAN_ARGS])
    with journal_path().open("a") as journal:
        journal.write("not json\n")
    capsys.readouterr()

    # When: Undoing the run
    exit_code = _run(["undo", "--force"])

    # Then: The file is restored and the warning names the journal and the line
    assert exit_code == 0
    assert file.exists()
    expected = JOURNAL_DAMAGED_LINES_IGNORED_MESSAGE.format(
        line_numbers="2", path=journal_path().relative_to(tmp_path)
    )
    captured = capsys.readouterr()
    assert _without_whitespace(expected) in _without_whitespace(captured.out + captured.err)


def test_undo_reports_an_undo_error(create_file, mocker, capsys) -> None:
    """Verify a failed move back is shown as an error with exit code 1, not a traceback."""
    # Given: A cleaned file, and moves that fail
    file = create_file("foo bar.txt")
    _run(["clean", str(file), *CLEAN_ARGS])
    mocker.patch.object(undoing, "move_file", side_effect=OSError("disk full"))
    capsys.readouterr()

    # When: Undoing the run
    exit_code = _run(["undo", "--force"])

    # Then: The command fails and shows the error
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "disk full" in captured.out + captured.err


def test_clean_and_undo_paths_with_markup_brackets(create_file, monkeypatch) -> None:
    """Verify paths that look like Rich markup survive the confirmation tables."""
    # Given: A file whose full path contains a Rich closing tag, `notes [/old] [draft].txt`
    file = create_file("old] [draft].txt", path="notes [")
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))

    # When: Cleaning it with confirmation, then undoing with confirmation
    clean_exit_code = _run(["clean", str(file), *CLEAN_ARGS, "--confirm", "-v"])
    assert not file.exists()
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    undo_exit_code = _run(["undo"])

    # Then: Both commands succeed and the file has its original name
    assert (clean_exit_code, undo_exit_code) == (0, 0)
    assert [path.name for path in file.parent.iterdir()] == [file.name]


def test_undo_reports_handled_files_before_an_error(create_file, tmp_path, mocker, capsys) -> None:
    """Verify a failed undo still reports the files it handled before the failure."""
    # Given: Two files cleaned in one run, where the file undo handles first has since vanished
    first = create_file("foo bar.txt")
    second = create_file("baz qux.txt")
    _run(["clean", str(first), str(second), *CLEAN_ARGS])
    handled_first, failing = reversed(read_journal(journal_path()).entries)
    handled_first.destination.unlink()
    mocker.patch.object(undoing, "move_file", side_effect=OSError("disk full"))
    capsys.readouterr()

    # When: Undoing the run
    exit_code = _run(["undo", "--force"])

    # Then: The command fails, names the missing file, and shows the error
    assert exit_code == 1
    output = _without_whitespace("".join(capsys.readouterr()))
    assert (
        _without_whitespace(
            f"{handled_first.destination.relative_to(tmp_path)} -> {handled_first.source.relative_to(tmp_path)}"
            f": {UNDO_OUTCOME_MESSAGES[UndoOutcome.NOT_FOUND]}"
        )
        in output
    )
    assert "diskfull" in output
    assert failing.destination.exists()


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores folder permissions")
@pytest.mark.parametrize("extra_args", [["-n"], ["--force"]], ids=["dry-run", "undo"])
def test_undo_reports_a_path_it_cannot_check(create_file, tmp_path, capsys, extra_args) -> None:
    """Verify an unreadable folder ends undo with an error naming the file, not a traceback."""
    # Given: A cleaned file inside a folder that is then made unreadable
    file = create_file("foo bar.txt", path="locked")
    _run(["clean", str(file), *CLEAN_ARGS])
    capsys.readouterr()
    file.parent.chmod(0)

    # When: Undoing the run
    try:
        exit_code = _run(["undo", *extra_args])
    finally:
        file.parent.chmod(0o700)

    # Then: The command fails, names the file, and leaves it where it is
    assert exit_code == 1
    assert _without_whitespace(
        str(file.with_name("foo-bar.txt").relative_to(tmp_path))
    ) in _without_whitespace("".join(capsys.readouterr()))
    assert file.with_name("foo-bar.txt").exists()


@pytest.mark.parametrize(
    ("extra_args", "backup_message", "backup_returned"),
    [
        pytest.param(["-n"], UNDO_BACKUP_WOULD_RETURN_MESSAGE, False, id="dry-run"),
        pytest.param(["--force"], UNDO_BACKUP_RESTORED_MESSAGE, True, id="undo"),
    ],
)
def test_undo_names_where_the_replaced_file_returns(
    create_file, tmp_path, capsys, extra_args, backup_message, backup_returned
) -> None:
    """Verify undo says that the file the run replaced returns from its backup."""
    # Given: A cleaned file that replaced another file, which was backed up
    file = create_file("foo bar.txt", content="new")
    replaced = create_file("foo-bar.txt", content="old")
    _run(["clean", str(file), *CLEAN_ARGS])
    (entry,) = read_journal(journal_path()).entries
    assert entry.backup is not None
    capsys.readouterr()

    # When: Undoing the run
    exit_code = _run(["undo", *extra_args])

    # Then: The output names the backup and the path it returns to
    assert exit_code == 0
    expected = backup_message.format(
        backup=entry.backup.relative_to(tmp_path), destination=replaced.relative_to(tmp_path)
    )
    assert _without_whitespace(expected) in _without_whitespace("".join(capsys.readouterr()))
    assert (replaced.read_text() == "old") == backup_returned
