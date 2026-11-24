"""Folder model."""

import functools
import re
from pathlib import Path

from nclutils import pp

from neatfile.constants import MATCHING_STOPWORDS, NEATFILE_IGNORE_NAME, NEATFILE_NAME, FolderType
from neatfile.utils.strings import (
    remove_inner_apostrophes,
    strip_special_chars,
    strip_stopwords,
    tokenize_string,
)


class Folder:
    """Represent a folder within a neatfile project.

    Args:
        path (Path): Path to the folder.
        folder_type (FolderType): Type of the folder.
        strip_stopwords (bool): Remove stopwords from the terms taken from the folder name.

    Attributes:
        path (Path): Path to the folder.
        type (FolderType): Type of the folder.
        number (str | None): The Johnny Decimal number of the folder.
        name (str): The name of the folder.
        terms (set[str]): Unique search terms from folder name and .neatfile contents.
    """

    def __init__(
        self,
        path: Path,
        folder_type: FolderType,
        *,
        strip_stopwords: bool,
    ) -> None:
        # Absolute but not resolved: resolving a symbolic link would place the folder outside its project
        self.path = Path(path).expanduser().absolute()
        self.type = folder_type
        self.strip_stopwords = strip_stopwords

    @functools.cached_property
    def is_ignored(self) -> bool:
        """Report whether a `.neatfileignore` marker excludes this folder from matching.

        Returns:
            bool: True when the folder holds a `.neatfileignore` file.
        """
        return (self.path / NEATFILE_IGNORE_NAME).exists()

    def __str__(self) -> str:  # pragma: no cover
        """Return string representation of the folder.

        Returns:
            str: String representation in format "FOLDER: name (type): path"
        """
        return f"FOLDER: {self.path.name} ({self.type.value}): {self.path}"

    @functools.cached_property
    def name(self) -> str:
        """Extract the name portion of the folder by removing the Johnny Decimal prefix.

        Returns:
            str: Name of the folder with JD prefix removed.
        """
        if self.type == FolderType.OTHER:
            return self.path.name

        return re.sub(pattern=self.type.pattern, repl="", string=self.path.name).strip()

    @functools.cached_property
    def number(self) -> str | None:
        """Extract the Johnny Decimal number from the folder name.

        Returns:
            str | None: The JD number if folder is a JD type and its name carries a JD prefix, None otherwise.
        """
        if self.type == FolderType.OTHER:
            return None

        match = re.match(pattern=self.type.pattern, string=self.path.name)
        return match.group(0).strip("- _") if match else None

    @functools.cached_property
    def terms(self) -> set[str]:
        """Extract searchable terms from the folder name and .neatfile configuration.

        Process the folder name into searchable tokens by removing special characters and stopwords. Additionally parse any terms defined in a `.neatfile` configuration file, excluding comments and duplicates.

        Returns:
            set[str]: Normalized set of search terms with special characters removed and converted to lowercase
        """
        terms = tokenize_string(remove_inner_apostrophes(self.name))
        terms = strip_special_chars(terms)

        if self.strip_stopwords:
            filtered_tokens = strip_stopwords(terms, stopwords=MATCHING_STOPWORDS)
            # Keep original tokens if stripping stopwords would remove everything
            terms = filtered_tokens or terms

        neatfile_path: Path = self.path / NEATFILE_NAME
        neatfile_lines: list[str]
        try:
            neatfile_lines = neatfile_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            neatfile_lines = []
        except (OSError, UnicodeDecodeError) as error:
            pp.warning(f"Ignoring {neatfile_path}: expected a readable UTF-8 text file ({error})")
            neatfile_lines = []
        terms.extend(line for line in neatfile_lines if not line.strip().startswith("#"))

        return {stripped for x in terms if (stripped := x.lower().strip())}
