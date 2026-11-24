"""Commit changes to files."""

import shutil
from dataclasses import dataclass
from pathlib import Path

from nclutils import pp
from nclutils.fs import backup_path, copy_file

from neatfile.models import File
from neatfile.utils.paths import path_exists

PARTIAL_MOVE_MESSAGE = (
    "Copied {source} to {destination}, but cannot delete the original: {error}. Both copies remain."
)
FAILED_COPY_AFTER_BACKUP_MESSAGE = "Cannot copy {source} to {destination}: {error}"
BACKUP_LOCATION_MESSAGE = "The earlier file at {destination} was backed up to {backup}."
HARD_LINK_MOVE_MESSAGE = "Cannot move {source} to {destination}: they are hard links to the same file, and moving would leave both names in place"
DESTINATION_NOT_A_FILE_MESSAGE = "Cannot move {source} to {destination}: the destination is a symbolic link, or a folder that would be deleted without a backup"


def with_backup_location(message: str, *, destination: Path, backup: Path | None) -> str:
    """Append where the replaced file was backed up, so an error never hides the backup.

    Args:
        message (str): The error message.
        destination (Path): The path the backed-up file was replaced at.
        backup (Path | None): The backup, or None when nothing was backed up.

    Returns:
        str: `message`, followed by the backup location when there is one.
    """
    if backup is None:
        return message
    return f"{message} {BACKUP_LOCATION_MESSAGE.format(destination=destination, backup=backup)}"


class MoveError(OSError):
    """Raise when a move fails after it changed the disk, so the error names every file it left behind."""

    def __init__(
        self, message: str, *, source: Path, destination: Path, backup: Path | None
    ) -> None:
        super().__init__(
            with_backup_location(message=message, destination=destination, backup=backup)
        )
        self.source = source
        self.destination = destination
        self.backup = backup


@dataclass(frozen=True)
class CommittedChange:
    """One file that was renamed or moved, with enough detail to record it for undo."""

    source: Path
    destination: Path
    backup: Path | None


def move_file(source: Path, destination: Path, *, keep_backup: bool) -> Path | None:
    """Move one file to a new path, optionally backing up a file it would replace.

    Works for any two paths so undo can move a file back the same way it was moved.

    Args:
        source: The file to move.
        destination: The path the file moves to.
        keep_backup: Back up a different file that already exists at `destination` before replacing it.

    Returns:
        Path | None: The backup of the replaced file, or None when nothing was backed up.

    Raises:
        MoveError: If the copy failed after the file at `destination` was backed up, or the copy at
            `destination` was made but `source` could not be deleted.
        OSError: If the file cannot be copied or backed up.
        ValueError: If the copy is refused.
        FileExistsError: If `destination` is a symbolic link, which copying would write through, or
            a folder that `keep_backup` is False for, which copying would delete.
        shutil.SameFileError: If `source` and `destination` are hard links to the same file.
    """
    if destination.is_symlink() or (destination.is_dir() and not keep_backup):
        msg = DESTINATION_NOT_A_FILE_MESSAGE.format(source=source, destination=destination)
        raise FileExistsError(msg)

    # On a case-insensitive filesystem a case-only rename resolves to the same file, which
    # copy_file refuses. Renaming in place is safe there because nothing else is overwritten.
    if path_exists(destination) and source.samefile(destination):
        source.rename(destination)
        # Renaming between two hard links of one file is a no-op. Compare the listed names,
        # because `exists()` cannot tell `Report.PDF` from `Report.pdf` on a case-insensitive disk.
        if source.name in {path.name for path in source.parent.iterdir()}:
            msg = HARD_LINK_MOVE_MESSAGE.format(source=source, destination=destination)
            raise shutil.SameFileError(msg)
        return None

    backup: Path | None = None
    if keep_backup and path_exists(destination):
        backup = backup_path(destination, console=pp.console(), strict=True)

    try:
        copy_file(source, destination, keep_backup=False, console=pp.console(), strict=True)
    except (OSError, ValueError) as error:
        if backup is None:
            raise
        raise MoveError(
            FAILED_COPY_AFTER_BACKUP_MESSAGE.format(
                source=source, destination=destination, error=error
            ),
            source=source,
            destination=destination,
            backup=backup,
        ) from error
    try:
        source.unlink()
    except OSError as error:
        # Keep the copy: it may already have replaced a file at the destination
        raise MoveError(
            PARTIAL_MOVE_MESSAGE.format(source=source, destination=destination, error=error),
            source=source,
            destination=destination,
            backup=backup,
        ) from error
    return backup


def commit_changes(
    file: File, *, dry_run: bool, keep_backup: bool, project_path: Path | None
) -> CommittedChange | None:
    """Rename or move a file to its new name and parent, or report the change on a dry run.

    Args:
        file (File): The file with its pending name and parent.
        dry_run (bool): Report the change without touching the file.
        keep_backup (bool): Back up a file that the new name would overwrite.
        project_path (Path | None): Root of the project the file moves into, used to shorten the reported path.

    Returns:
        CommittedChange | None: The change made, or None when the file has no changes, the run is a dry run, or the change failed.
    """
    if not file.has_changes:
        pp.info(f"{file.name} -> No changes")
        return None

    if file.has_new_parent and project_path is not None:
        msg_file_name = f"{file.new_parent.relative_to(project_path)}/{file.new_name}"
    else:
        msg_file_name = file.new_name

    if dry_run:
        pp.dryrun(f"{file.name} -> {msg_file_name}")
        return None

    # Resolve only the folders: `..` segments in a journal path stop undo once a folder they pass
    # through is gone, and resolving the file name would follow a symbolic link at the destination
    source = file.path.parent.resolve() / file.path.name
    destination = file.new_parent.resolve() / file.new_name
    try:
        backup = move_file(source=source, destination=destination, keep_backup=keep_backup)
    except (OSError, ValueError) as e:
        pp.error(f"Cannot move {file.name}: {e}")
        return None

    pp.success(f"{file.name} -> {msg_file_name}")
    return CommittedChange(source=source, destination=destination, backup=backup)
