"""File model."""

import difflib
from pathlib import Path

from rich.text import Text

from neatfile.constants import COMPOUND_EXTENSIONS
from neatfile.utils.paths import display_path


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
    return path.stem, path.suffix


class File:
    """Track a file's current location and its planned name and parent, so callers can preview a change before applying it."""

    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.stem, self.suffix = _split_extension(self.name)
        self.suffixes = self.path.suffixes
        self.parent = self.path.parent

        self.is_dotfile = self.stem.startswith(".")

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
    def new_path(self) -> Path:
        """Return the full path the file will have after the change is applied."""
        return Path(self.new_parent / self.new_name)

    @property
    def has_new_parent(self) -> bool:
        """Report whether the file is planned to move to a different folder."""
        return self.parent != self.new_parent

    @property
    def has_changes(self) -> bool:
        """Report whether the planned name or parent differs from the current one."""
        return self.has_new_name or self.has_new_parent

    @property
    def display_path(self) -> Path:
        """Return the path to show in messages, relative to the current directory when possible."""
        return display_path(self.path)

    def get_filename_diff(self) -> Text:
        """Compare original and new filenames and highlight their differences, so a user can review a rename.

        Highlight insertions in green and deletions in red.

        Returns:
            Text: The original filename with deleted and inserted fragments highlighted.
        """
        matcher = difflib.SequenceMatcher(None, self.name, self.new_name)
        inserted, deleted = "green reverse", "red reverse"
        diff = Text()

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                diff.append(self.name[i1:i2])
            if tag in {"delete", "replace"}:
                diff.append(self.name[i1:i2], style=deleted)
            if tag in {"insert", "replace"}:
                diff.append(self.new_name[j1:j2], style=inserted)

        return diff
