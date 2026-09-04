"""Folder model."""

import functools
import re
from pathlib import Path

from neatfile import settings
from neatfile.constants import NEATFILE_IGNORE_NAME, NEATFILE_NAME, FolderType
from neatfile.utils.strings import strip_special_chars, strip_stopwords, tokenize_string


class Folder:
    """Represent a folder within a neatfile project.

    Args:
        path (Path): Path to the folder.
        folder_type (FolderType): Type of the folder.
        area (Path | None, optional): Path to the area folder, if the folder is a category or subcategory. Defaults to None.
        category (Path | None, optional): Path to the category folder, if the folder is a subcategory. Defaults to None.

    Attributes:
        path (Path): Path to the folder.
        type (FolderType): Type of the folder.
        area (Path | None): Path to the area folder, if the folder is a category or subcategory.
        category (Path | None): Path to the category folder, if the folder is a subcategory.
        number (str | None): The Johnny Decimal number of the folder.
        name (str): The name of the folder.
        terms (list[str]): List of unique search terms from folder name and .neatfile contents.
    """

    def __init__(
        self,
        path: Path,
        folder_type: FolderType,
        area: Path | None = None,
        category: Path | None = None,
    ) -> None:
        self.path = Path(path).expanduser().resolve()
        self.type = folder_type
        self.area = area
        self.category = category
        self.is_ignored = Path(self.path, NEATFILE_IGNORE_NAME).exists()

    def __str__(self) -> str:  # pragma: no cover
        """Return string representation of the folder.

        Returns:
            str: String representation in format "FOLDER: name (type): path"
        """
        return f"FOLDER: {self.path.name} ({self.type.value}): {self.path}"

    @property
    def name(self) -> str:
        """Extract the name portion of the folder by removing the Johnny Decimal prefix.

        Returns:
            str: Name of the folder with JD prefix removed.
        """
        if self.type == FolderType.OTHER:
            return self.path.name

        return re.sub(self.type.pattern, "", self.path.name).strip()

    @property
    def number(self) -> str | None:
        """Extract the Johnny Decimal number from the folder name.

        Returns:
            str | None: The JD number if folder is a JD type and its name carries a JD prefix, None otherwise.
        """
        if self.type == FolderType.OTHER:
            return None

        match = re.match(self.type.pattern, self.path.name)
        return match.group(0).strip("- _") if match else None

    @functools.cached_property
    def terms(self) -> set[str]:
        """Extract searchable terms from the folder name and .neatfile configuration.

        Process the folder name into searchable tokens by removing special characters and stopwords. Additionally parse any terms defined in a `.neatfile` configuration file, excluding comments and duplicates.

        Returns:
            set[str]: Normalized set of search terms with special characters removed and converted to lowercase
        """
        terms = tokenize_string(self.name)
        terms = strip_special_chars(terms)

        if settings.strip_stopwords:
            filtered_tokens = strip_stopwords(terms)
            # Keep original tokens if stripping stopwords would remove everything
            terms = filtered_tokens or terms

        if Path(self.path, NEATFILE_NAME).exists():
            content = Path(self.path, NEATFILE_NAME).read_text(encoding="utf-8").splitlines()
            for line in content:
                if line.startswith("#") or line in terms:
                    continue
                terms.append(line)

        return {stripped for x in terms if (stripped := x.lower().strip())}
