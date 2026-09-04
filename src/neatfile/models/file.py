"""File model."""

import difflib
from pathlib import Path

from neatfile.constants import COMPOUND_EXTENSIONS, Separator
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
    """File model."""

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
