"""Test moving files on commit."""

import errno
import os
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from neatfile.features.committing import (
    BACKUP_LOCATION_MESSAGE,
    HARD_LINK_MOVE_MESSAGE,
    SOURCE_INSIDE_DESTINATION_MESSAGE,
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


def test_move_file_refuses_to_replace_the_folder_that_holds_the_source(tmp_path: Path) -> None:
    """Verify a move onto a folder that contains the source fails and changes nothing."""
    # Given: A file inside the folder it would replace
    destination = tmp_path / "report"
    destination.mkdir()
    source = destination / "report.txt"
    source.write_text("content")
    before = sorted(tmp_path.rglob("*"))

    # When/Then: The move fails, and the file and its folder stay in place
    expected = SOURCE_INSIDE_DESTINATION_MESSAGE.format(source=source, destination=destination)
    with pytest.raises(FileExistsError, match=re.escape(expected)):
        move_file(source=source, destination=destination, keep_backup=True)
    assert sorted(tmp_path.rglob("*")) == before
    assert source.read_text() == "content"


def _fail_cross_device(path: Path, target: Path) -> Path:
    raise OSError(errno.EXDEV, "Invalid cross-device link", str(path))


def _fail_rename(path: Path, target: Path) -> Path:
    raise PermissionError(errno.EPERM, "Operation not permitted", str(path))


def test_move_file_renames_on_same_filesystem(tmp_path: Path) -> None:
    """Verify a move on one filesystem keeps the same file and creates missing folders."""
    # Given: A file, and a destination in a folder that does not exist yet
    source = tmp_path / "new.txt"
    source.write_text("new")
    original_inode = source.stat().st_ino
    destination = tmp_path / "nested" / "folder" / "moved.txt"

    # When: Moving the file
    backup = move_file(source=source, destination=destination, keep_backup=True)

    # Then: The destination is the same file, not a copy, and the original name is gone
    assert backup is None
    assert destination.stat().st_ino == original_inode
    assert destination.read_text() == "new"
    assert not source.exists()


@pytest.mark.parametrize("keep_backup", [True, False])
@pytest.mark.parametrize(
    "rename_errno",
    [
        pytest.param(errno.EXDEV, id="different-filesystem"),
        pytest.param(errno.ENOTSUP, id="rename-unsupported"),
        pytest.param(errno.ENOSYS, id="rename-not-implemented"),
    ],
)
def test_move_file_copies_when_a_rename_cannot_move_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, keep_backup: bool, rename_errno: int
) -> None:
    """Verify a move that a rename cannot make copies the file, then deletes the original."""
    # Given: A destination that is taken, and a rename the filesystem cannot make
    source = tmp_path / "new.txt"
    source.write_text("new")
    destination = tmp_path / "taken.txt"
    destination.write_text("old")

    def _fail_rename_with_errno(path: Path, target: Path) -> Path:
        raise OSError(rename_errno, os.strerror(rename_errno), str(path))

    monkeypatch.setattr("pathlib.Path.replace", _fail_rename_with_errno)

    # When: Moving the file
    backup = move_file(source=source, destination=destination, keep_backup=keep_backup)

    # Then: The destination holds the moved file, and the replaced file is backed up on request
    assert destination.read_text() == "new"
    assert not source.exists()
    assert (backup.read_text() if backup else None) == ("old" if keep_backup else None)


@pytest.mark.parametrize("cross_device", [False, True], ids=["rename", "copy"])
def test_move_file_moves_a_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cross_device: bool
) -> None:
    """Verify a folder moves with its contents, so undo can return a folder backup."""
    # Given: A folder with a file inside, on the same or what reports as a different filesystem
    source = tmp_path / "backup.bak"
    source.mkdir()
    (source / "inside.txt").write_text("kept")
    destination = tmp_path / "restored"
    if cross_device:
        monkeypatch.setattr("pathlib.Path.replace", _fail_cross_device)

    # When: Moving the folder
    backup = move_file(source=source, destination=destination, keep_backup=False)

    # Then: The folder and its contents are at the destination, and the original is gone
    assert backup is None
    assert (destination / "inside.txt").read_text() == "kept"
    assert not source.exists()


def test_move_file_copies_the_target_of_a_symbolic_link(tmp_path: Path) -> None:
    """Verify moving a symbolic link leaves a regular file with the linked content."""
    # Given: A symbolic link to a file
    target = tmp_path / "target.txt"
    target.write_text("linked")
    source = tmp_path / "link.txt"
    source.symlink_to(target)
    destination = tmp_path / "moved.txt"

    # When: Moving the link
    move_file(source=source, destination=destination, keep_backup=True)

    # Then: The destination is a regular file, and the link's target is untouched
    assert not destination.is_symlink()
    assert destination.read_text() == "linked"
    assert not source.exists()
    assert target.read_text() == "linked"


def test_move_file_without_backup_raises_the_rename_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a failed move with nothing backed up raises its own error and keeps the source."""
    # Given: A rename that fails
    source = tmp_path / "new.txt"
    source.write_text("new")
    monkeypatch.setattr("pathlib.Path.replace", _fail_rename)

    # When/Then: The rename error is raised and the source is untouched
    with pytest.raises(PermissionError):
        move_file(source=source, destination=tmp_path / "moved.txt", keep_backup=True)
    assert source.read_text() == "new"


def _fail_copy(*args: object, **kwargs: object) -> None:
    msg = "disk full"
    raise OSError(msg)


def _fail_source_delete(path: Path, *, missing_ok: bool = False) -> None:
    msg = "permission denied"
    raise PermissionError(msg)


@pytest.mark.parametrize(
    "failures",
    [
        pytest.param({"pathlib.Path.replace": _fail_rename}, id="rename-fails"),
        pytest.param(
            {
                "pathlib.Path.replace": _fail_cross_device,
                "neatfile.features.committing.copy_file": _fail_copy,
            },
            id="copy-fails",
        ),
        pytest.param(
            {
                "pathlib.Path.replace": _fail_cross_device,
                "pathlib.Path.unlink": _fail_source_delete,
            },
            id="delete-fails",
        ),
    ],
)
def test_move_file_error_names_the_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failures: dict[str, Callable[..., object]],
) -> None:
    """Verify a move that fails after backing up the replaced file says where the backup is."""
    # Given: A destination that is already taken, and a step after the backup that fails
    source = tmp_path / "new.txt"
    source.write_text("new")
    destination = tmp_path / "taken.txt"
    destination.write_text("old")
    for target, replacement in failures.items():
        monkeypatch.setattr(target, replacement)

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
