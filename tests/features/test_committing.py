"""Test moving files on commit."""

import os
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from neatfile.features.committing import (
    BACKUP_LOCATION_MESSAGE,
    HARD_LINK_MOVE_MESSAGE,
    MoveError,
    move_file,
)


def test_move_file_refuses_hard_links_to_one_file(tmp_path: Path) -> None:
    """Verify moving onto another hard link of the same file fails instead of doing nothing."""
    # Given: Two names that are hard links to one file
    source = tmp_path / "original.txt"
    source.write_text("content")
    destination = tmp_path / "linked.txt"
    os.link(source, destination)

    # When/Then: Moving one onto the other fails and names both paths
    expected = HARD_LINK_MOVE_MESSAGE.format(source=source, destination=destination)
    with pytest.raises(OSError, match=re.escape(expected)):
        move_file(source=source, destination=destination, keep_backup=True)
    assert source.exists()
    assert destination.exists()


def _make_folder(path: Path) -> None:
    path.mkdir()
    (path / "inside.txt").write_text("kept")


def _make_symlink(path: Path) -> None:
    target = path.with_name("target.txt")
    target.write_text("kept")
    path.symlink_to(target)


@pytest.mark.parametrize(
    ("make_destination", "keep_backup"),
    [
        pytest.param(_make_folder, False, id="folder-without-backup"),
        pytest.param(_make_symlink, False, id="symlink-without-backup"),
        pytest.param(_make_symlink, True, id="symlink-with-backup"),
    ],
)
def test_move_file_refuses_a_destination_that_is_not_a_file(
    tmp_path: Path, make_destination: Callable[[Path], None], keep_backup: bool
) -> None:
    """Verify a move that would write through a symbolic link or delete a folder fails and changes nothing."""
    # Given: A file, and a folder or symbolic link at its new name
    source = tmp_path / "new.txt"
    source.write_text("new")
    destination = tmp_path / "taken"
    make_destination(destination)
    before = sorted(tmp_path.rglob("*"))

    # When/Then: The move fails without changing anything
    with pytest.raises(OSError, match=re.escape(str(destination))):
        move_file(source=source, destination=destination, keep_backup=keep_backup)
    assert sorted(tmp_path.rglob("*")) == before
    assert source.read_text() == "new"
    assert (destination / "inside.txt" if destination.is_dir() else destination).read_text() == (
        "kept"
    )


def _fail_copy(*args: object, **kwargs: object) -> None:
    msg = "disk full"
    raise OSError(msg)


def _fail_source_delete(path: Path, *, missing_ok: bool = False) -> None:
    msg = "permission denied"
    raise PermissionError(msg)


@pytest.mark.parametrize(
    ("patched_target", "replacement"),
    [
        pytest.param("neatfile.features.committing.copy_file", _fail_copy, id="copy-fails"),
        pytest.param("pathlib.Path.unlink", _fail_source_delete, id="delete-fails"),
    ],
)
def test_move_file_error_names_the_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    patched_target: str,
    replacement: Callable[..., None],
) -> None:
    """Verify a move that fails after backing up the replaced file says where the backup is."""
    # Given: A destination that is already taken, and a step after the backup that fails
    source = tmp_path / "new.txt"
    source.write_text("new")
    destination = tmp_path / "taken.txt"
    destination.write_text("old")
    monkeypatch.setattr(patched_target, replacement)

    # When: Moving with a backup
    with pytest.raises(MoveError) as error_info:
        move_file(source=source, destination=destination, keep_backup=True)

    # Then: The error names the backup, which holds the replaced file
    backup = error_info.value.backup
    assert backup is not None
    assert backup.read_text() == "old"
    assert BACKUP_LOCATION_MESSAGE.format(destination=destination, backup=backup) in str(
        error_info.value
    )
