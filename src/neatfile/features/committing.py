"""Commit changes to files."""

import shutil

from nclutils import pp
from nclutils.fs import copy_file

from neatfile import settings
from neatfile.models import File


def commit_changes(file: File) -> bool:
    """Commit changes to files.

    Returns:
        bool: True if the file was committed, False if it was not
    """
    if not file.has_changes:
        pp.info(f"{file.name} -> No changes")
        return False

    if not file.has_new_parent:
        msg_file_name = file.new_name
    else:
        msg_file_name = f"{file.new_parent.relative_to(settings.project.path)}/{file.new_name}"

    if settings.dryrun:
        pp.dryrun(f"{file.name} -> {msg_file_name}")
        return True

    try:
        new_file = copy_file(
            file.path,
            file.new_path,
            keep_backup=not settings.overwrite,
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
