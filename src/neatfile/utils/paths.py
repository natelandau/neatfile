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
