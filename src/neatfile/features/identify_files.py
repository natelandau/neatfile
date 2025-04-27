"""Identify files which can be processed from a list of paths."""

import re
from pathlib import Path

import cappa

from neatfile import settings
from neatfile.constants import ALWAYS_IGNORE_FILES_REGEXES, SPINNER
from neatfile.utils import console, pp


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


def _process_path(path: Path, files: list[Path], start_path: Path) -> None:
    """Process a path and add any valid files to the list of processable files.

    Recursively walk through directories up to the configured project depth, evaluating each path against ignore rules. Add valid files to the provided files list.

    Args:
        path (Path): The path to process
        files (list[Path]): List to store found processable files
        start_path (Path): Original starting path used to calculate relative depth

    Raises:
        cappa.Exit: If the path does not exist
    """
    try:
        display_path = path.relative_to(Path.cwd())
    except ValueError:
        display_path = path

    if not path.exists():
        pp.error(f"Not found: `{display_path}`")
        raise cappa.Exit(code=1)

    if path.is_symlink():
        pp.warning(f"Symlink: `{display_path}`")
        return

    if _is_ignored_file(path):
        if pp.is_debug:
            pp.secondary(f"Ignored: `{display_path}`")
        return

    if path.is_file():
        files.append(path.absolute())
        return

    if path.is_dir():
        # Recursively walk directory tree to find all files
        for f in path.rglob("*"):
            # Calculate depth relative to starting path to enforce file_search_depth limit
            depth_of_file = len(f.relative_to(start_path).parts)

            if depth_of_file <= settings.get("file_search_depth", 1):
                _process_path(path=f, files=files, start_path=start_path)


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
    with console.status(
        "Processing Files...  [dim](Can take a while for large directory trees)[/]",
        spinner=SPINNER,
    ):
        for path in paths:
            file_path = path.expanduser().absolute()
            _process_path(path=file_path, files=files, start_path=file_path)

    if not files:
        pp.error("No files found. Run with `-v` to see what files are being ignored.")
        raise cappa.Exit(code=1)

    return sorted(set(files))
