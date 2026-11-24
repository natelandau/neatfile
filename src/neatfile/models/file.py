"""File model."""

import re
from pathlib import Path

from neatfile.constants import COMPOUND_EXTENSIONS

# Text after the last dot counts as an extension only when it is one alphanumeric word, so a name
# like "Report v1.2 final" keeps "2 final" in its stem
_EXTENSION_PATTERN = re.compile(r"\.[A-Za-z0-9]+")


def _split_extension(name: str) -> tuple[str, str]:
    """Split a filename into stem and extension, keeping compound extensions whole.

    Args:
        name (str): The filename to split.

    Returns:
        tuple[str, str]: The stem and the extension, where the extension keeps its original case.
    """
    lowered = name.lower()
    for ext in COMPOUND_EXTENSIONS:
        # Require a non-empty stem so a name like ".tar.gz" is a dotfile, not a bare extension
        if lowered.endswith(ext) and len(name) > len(ext):
            return name[: -len(ext)], name[-len(ext) :]

    path = Path(name)
    if _EXTENSION_PATTERN.fullmatch(path.suffix):
        return path.stem, path.suffix
    return name, ""


class File:
    """Track a file's current location and its planned name and parent, so callers can preview a change before applying it."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.name = path.name
        self.stem, self.suffix = _split_extension(self.name)
        self.parent = self.path.parent

        self.new_stem = self.stem
        self.new_suffix = self.suffix
        self.new_parent = self.parent

    @property
    def new_name(self) -> str:
        """Return the filename, stem plus suffix, the file will have after the change is applied."""
        return f"{self.new_stem}{self.new_suffix}"

    @property
    def has_new_name(self) -> bool:
        """Report whether the planned name differs from the current name."""
        return self.name != self.new_name

    @property
    def has_new_parent(self) -> bool:
        """Report whether the file is planned to move to a different folder.

        Compare resolved folders so the same folder reached through a symbolic link is not a move.
        """
        return self.parent.resolve() != self.new_parent.resolve()

    @property
    def has_changes(self) -> bool:
        """Report whether the planned name or parent differs from the current one."""
        return self.has_new_name or self.has_new_parent
