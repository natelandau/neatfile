"""Identify files which can be processed from a list of paths."""

import os
import re
from pathlib import Path

import cappa
from nclutils import pp

from neatfile import settings
from neatfile.constants import ALWAYS_IGNORE_FILES_REGEXES


def _is_ignored_file(file: Path) -> bool:
    """Check if a file matches any ignore patterns or rules.

    Evaluate the file against multiple ignore conditions including dotfiles, explicitly ignored files, regex patterns, and always-ignored file patterns. Used to filter out files that should not be processed.

    Args:
        file (Path): The file path to evaluate

    Returns:
        bool: True if the file should be ignored, False if it should be processed
    """
    return (
        (settings.ignore_dotfiles and file.name.startswith("."))
        or (file.name in settings.ignored_files)
        or re.search(settings.ignore_file_regex, file.name) is not None
        or any(re.search(regex, str(file)) for regex in ALWAYS_IGNORE_FILES_REGEXES)
    )


def _display_path(path: Path) -> Path:
    """Shorten a path for messages by making it relative to the current directory when possible.

    Args:
        path (Path): The path to shorten

    Returns:
        Path: The path relative to the current directory, or the original path when it lies outside it
    """
    try:
        return path.relative_to(Path.cwd())
    except ValueError:
        return path


def _process_file(path: Path, files: list[Path]) -> None:
    """Add a file to the list of processable files unless it is a symlink or matches an ignore rule.

    Args:
        path (Path): The file to evaluate
        files (list[Path]): List to store found processable files
    """
    if path.is_symlink():
        pp.warning(f"Symlink: `{_display_path(path)}`")
        return

    if _is_ignored_file(path):
        pp.debug(f"Ignored: `{_display_path(path)}`")
        return

    files.append(path.absolute())


def _walk_directory(directory: Path, files: list[Path]) -> None:
    """Walk a directory down to the configured search depth and collect processable files.

    The ignore rules judge file names, so a directory named on the command line is always entered even when its own name would be ignored. Subdirectories met during the walk are pruned when their name matches an ignore rule or when they are symlinks.

    Args:
        directory (Path): The directory to walk
        files (list[Path]): List to store found processable files
    """
    max_depth = settings.get("file_search_depth", 1)

    for root, dirnames, filenames in os.walk(directory):
        root_path = Path(root)
        depth = len(root_path.relative_to(directory).parts) + 1  # depth of files directly in root

        if depth >= max_depth:
            dirnames.clear()
        if depth > max_depth:  # Only when the configured depth is below 1
            continue

        # Prune in place so os.walk never enters skipped subdirectories
        for dirname in list(dirnames):
            subdirectory = root_path / dirname
            if subdirectory.is_symlink():
                pp.warning(f"Symlink: `{_display_path(subdirectory)}`")
                dirnames.remove(dirname)
            elif _is_ignored_file(subdirectory):
                pp.debug(f"Ignored: `{_display_path(subdirectory)}`")
                dirnames.remove(dirname)

        for filename in filenames:
            _process_file(root_path / filename, files)


def _process_path(path: Path, files: list[Path]) -> None:
    """Process a path and add any valid files to the list of processable files.

    Args:
        path (Path): The path to process
        files (list[Path]): List to store found processable files

    Raises:
        cappa.Exit: If the path does not exist
    """
    if not path.exists():
        pp.error(f"Not found: `{_display_path(path)}`")
        raise cappa.Exit(code=1)

    if path.is_dir() and not path.is_symlink():
        _walk_directory(path, files)
        return

    _process_file(path, files)


def find_processable_files(paths: list[Path]) -> list[Path]:
    """Recursively find all processable files from a list of paths.

    Search through the provided paths and their subdirectories to find files that should be processed, excluding symlinks and ignored files. For directories, only search to the configured project depth.

    Args:
        paths (list[Path]): List of file or directory paths to search

    Returns:
        list[Path]: Sorted list of absolute paths to processable files

    Raises:
        cappa.Exit: If no processable files are found
    """
    if not paths:
        return []

    files: list[Path] = []
    with pp.step(
        "Processing Files...",
    ):
        for path in paths:
            file_path = path.expanduser().absolute()
            _process_path(path=file_path, files=files)

    if not files:
        pp.error("No files found. Run with `-v` to see what files are being ignored.")
        raise cappa.Exit(code=1)

    return sorted(set(files))
