"""File model."""

import difflib
from pathlib import Path

from neatfile.constants import Separator
from neatfile.utils.strings import guess_separator


class File:
    """File model."""

    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        # Path.stem only removes the last extension, but we need to handle multiple extensions
        # e.g. for "file.tar.gz", Path.stem returns "file.tar" but we want "file"
        self.stem = self.path.stem
        self.suffix = self.path.suffix
        self.suffixes = self.path.suffixes
        self.parent = self.path.parent

        self.is_dotfile = self.stem.startswith(".")

        self.new_stem = self.stem
        self.new_suffix = self.suffix
        self.new_parent = self.parent

    @property
    def new_name(self) -> str:
        """New name."""
        return f"{self.new_stem}{self.new_suffix}"

    @property
    def has_new_name(self) -> bool:
        """True if the file has changes in it's name."""
        return self.name != self.new_name

    @property
    def new_path(self) -> Path:
        """New path."""
        return Path(self.new_parent / self.new_name)

    @property
    def has_new_parent(self) -> bool:
        """True if the file has a new parent."""
        return self.parent != self.new_parent

    @property
    def has_changes(self) -> bool:
        """True if the file has changes in it's name or parent."""
        return self.has_new_name or self.has_new_parent

    @property
    def display_path(self) -> Path:
        """Display path."""
        try:
            return self.path.relative_to(Path.cwd())
        except ValueError:
            return self.path

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
        """Guess the separator of the filename.

        Returns:
            Separator: The guessed separator of the filename.
        """
        return guess_separator(self.new_stem)
