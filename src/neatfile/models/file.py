"""File model."""

import difflib
from pathlib import Path

from neatfile.constants import COMPOUND_EXTENSIONS, Separator
from neatfile.utils.paths import display_path
from neatfile.utils.strings import guess_separator


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

    def get_filename_diff(self) -> str:
        """Compare original and new filenames and highlight their differences.

        Generate a visual diff by comparing the original filename against the new name. Highlight insertions in green and deletions in red using rich markup syntax.

        Returns:
            str: A rich-formatted string showing differences between original and new filenames
        """
        matcher = difflib.SequenceMatcher(None, self.name, self.new_name)

        # Color codes for highlighting differences in the output
        green, red, end_color = "[green reverse]", "[red reverse]", "[/]"
        diff_output = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                diff_output.append(self.name[i1:i2])
            elif tag == "insert":
                diff_output.append(f"{green}{self.new_name[j1:j2]}{end_color}")
            elif tag == "delete":
                diff_output.append(f"{red}{self.name[i1:i2]}{end_color}")
            elif tag == "replace":
                diff_output.extend(
                    [
                        f"{red}{self.name[i1:i2]}{end_color}",
                        f"{green}{self.new_name[j1:j2]}{end_color}",
                    ]
                )

        return "".join(diff_output)

    def guess_separator(self) -> Separator:
        """Guess the word separator from the pending new stem.

        Read `new_stem`, not the original stem, so the guess reflects edits already made, such as a removed date.

        Returns:
            Separator: The most common separator in `new_stem`, or underscore when it has none.
        """
        return guess_separator(self.new_stem)
