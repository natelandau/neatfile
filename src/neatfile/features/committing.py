"""Commit changes to files."""

import shutil
from pathlib import Path

from nclutils import pp
from nclutils.fs import copy_file

from neatfile.models import File


def commit_changes(
    file: File, *, dry_run: bool, keep_backup: bool, project_path: Path | None
) -> bool:
    """Rename or move a file to its new name and parent, or report the change on a dry run.

    Args:
        file (File): The file with its pending name and parent.
        dry_run (bool): Report the change without touching the file.
        keep_backup (bool): Back up a file that the new name would overwrite.
        project_path (Path | None): Root of the project the file moves into, used to shorten the reported path.

    Returns:
        bool: True if the file was committed, False if it was not
    """
    if not file.has_changes:
        pp.info(f"{file.name} -> No changes")
        return False

    if file.has_new_parent and project_path is not None:
        msg_file_name = f"{file.new_parent.relative_to(project_path)}/{file.new_name}"
    else:
        msg_file_name = file.new_name

    if dry_run:
        pp.dryrun(f"{file.name} -> {msg_file_name}")
        return True

    # On a case-insensitive filesystem a case-only rename resolves to the same file, which
    # copy_file refuses. Renaming in place is safe there because nothing else is overwritten.
    if file.new_path.exists() and file.path.samefile(file.new_path):
        file.path.rename(file.new_path)
        pp.success(f"{file.name} -> {msg_file_name}")
        return True

    try:
        new_file = copy_file(
            file.path,
            file.new_path,
            keep_backup=keep_backup,
            console=pp.console(),
            strict=True,
        )
    except (ValueError, shutil.SameFileError) as e:
        pp.error(f"Error copying file: {e}")
        return False

    if new_file:
        file.path.unlink()
        pp.success(f"{file.name} -> {msg_file_name}")
        return True

    pp.error(f"{file.name} -> {msg_file_name}")
    return False
