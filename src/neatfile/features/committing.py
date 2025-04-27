"""Commit changes to files."""

from pathlib import Path

from neatfile import settings
from neatfile.constants import Separator
from neatfile.models import File
from neatfile.utils import pp


def unique_filename(file: File) -> Path:
    """Generate a unique filename by appending an incrementing number.

    Append an incrementing number to the filename stem using the configured separator character until finding an unused name. When continue_sequence is True, strip any existing number suffix before incrementing to continue an existing sequence. Preserves the original file extension.

    Args:
        file (File): The file model containing the path to make unique

    Returns:
        Path: A unique path that does not exist in the target directory
    """
    if not file.new_path.exists():
        return file.new_path

    sep = "_" if settings.separator == Separator.IGNORE else settings.separator.value

    original_stem = file.new_path.stem

    i = 1
    path = file.new_path
    while path.exists():
        path = path.with_name(f"{original_stem}{sep}{i}{path.suffix}")
        i += 1

    file.new_stem = path.stem
    return file.new_path


def commit_changes(file: File) -> bool:
    """Commit changes to files.

    Returns:
        bool: True if the file was committed, False if it was not
    """
    if not file.has_changes:
        pp.info(f"{file.name} -> No changes")
        return False

    if not settings.overwrite or file.new_path.is_dir():
        target_path = unique_filename(file)
    else:
        target_path = file.new_path

    if not file.has_new_parent:
        msg_file_name = file.new_name
    else:
        msg_file_name = f"{file.new_parent.relative_to(settings.project.path)}/{file.new_name}"

    if settings.dryrun:
        pp.dryrun(f"{file.name} -> {msg_file_name}")
        return True

    file.path.rename(target_path)
    pp.success(f"{file.name} -> {msg_file_name}")
    return True
