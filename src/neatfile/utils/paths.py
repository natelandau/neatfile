"""Path utilities."""

from pathlib import Path


def display_path(path: Path) -> Path:
    """Shorten a path for messages by making it relative to the current directory when possible.

    Args:
        path (Path): The path to shorten.

    Returns:
        Path: The path relative to the current directory, or the original path when it lies outside it.
    """
    try:
        return path.relative_to(Path.cwd())
    except ValueError:
        return path


def path_exists(path: Path) -> bool:
    """Report whether a path exists, raising when the answer is unknown, so a file is never treated as gone by mistake.

    `Path.exists` returns False for some errors, such as a folder without read permission on newer
    Python versions.

    Args:
        path (Path): The path to check.

    Returns:
        bool: True when the path exists, False when it or a parent folder is absent.

    Raises:
        OSError: If `path` cannot be checked for a reason other than being absent.
    """
    try:
        path.stat()
    except (FileNotFoundError, NotADirectoryError):
        return False
    return True


def is_case_only_rename(source: Path, destination: Path) -> bool:
    """Report whether `source` exists only because a case-insensitive disk resolves it to `destination`.

    Call it before treating an existing `source` as a different file. Hard links also pass
    `samefile`, but they are two real names, so the names must match too.

    Args:
        source (Path): The path that appears to exist.
        destination (Path): The path it may resolve to.

    Returns:
        bool: True when both paths name one file in one folder and differ only in letter case.

    Raises:
        OSError: If either path cannot be checked.
    """
    return (
        source.samefile(destination)
        and source.parent.samefile(destination.parent)
        and source.name.casefold() == destination.name.casefold()
    )
