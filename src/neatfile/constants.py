"""Constants for the neatfile package."""

import os
from enum import Enum
from pathlib import Path

PACKAGE_NAME = __package__.replace("_", "-").replace(".", "-").replace(" ", "-")
CONFIG_DIR = Path(os.getenv("XDG_CONFIG_HOME", "~/.config")).expanduser().absolute() / PACKAGE_NAME
DATA_DIR = Path(os.getenv("XDG_DATA_HOME", "~/.local/share")).expanduser().absolute() / PACKAGE_NAME
STATE_DIR = (
    Path(os.getenv("XDG_STATE_HOME", "~/.local/state")).expanduser().absolute() / PACKAGE_NAME
)
CACHE_DIR = Path(os.getenv("XDG_CACHE_HOME", "~/.cache")).expanduser().absolute() / PACKAGE_NAME
PROJECT_ROOT_PATH = Path(__file__).parents[2].absolute()
PACKAGE_ROOT_PATH = Path(__file__).parents[0].absolute()

DEFAULT_CONFIG_PATH = PACKAGE_ROOT_PATH / "default_config.toml"
USER_CONFIG_PATH = CONFIG_DIR / "config.toml"
DEV_DIR = PROJECT_ROOT_PATH / ".development"
DEV_CONFIG_PATH = DEV_DIR / "dev-config.toml"
VERSION = "4.0.0"
ALWAYS_IGNORE_FILES_REGEXES = [r"\.DS_Store$", r"\.neatfile$", r"\.stignore$", r"__pycache__"]
SPINNER = "bouncingBall"
NEATFILE_NAME = ".neatfile"
NEATFILE_IGNORE_NAME = ".neatfileignore"


class PrintLevel(Enum):
    """Define verbosity levels for console output.

    Use these levels to control the amount of information displayed to users. Higher levels include all information from lower levels plus additional details.
    """

    INFO = 0
    DEBUG = 1
    TRACE = 2


class FolderType(str, Enum):
    """Enum for folder types."""

    AREA = "area"
    CATEGORY = "category"
    SUBCATEGORY = "subcategory"
    OTHER = "other"

    @property
    def pattern(self) -> str:
        r"""Get the regex pattern for the folder type.

        Returns:
            str: The regex pattern for the folder type.

        Raises:
            ValueError: If the folder type is unknown.

        Example:
            >>> FolderType.AREA.pattern
            '^\\d{2}-\\d{2}[- _]'
            >>> FolderType.CATEGORY.pattern
            '^\\d{2}[- _]'
            >>> FolderType.SUBCATEGORY.pattern
            '^\\d{2}\\.\\d{2}[- _]'
            >>> FolderType.OTHER.pattern
            Traceback (most recent call last):
            ValueError: Unknown folder type: other
        """
        match self:
            case FolderType.AREA:
                return r"^\d{2}-\d{2}[- _]"
            case FolderType.CATEGORY:
                return r"^\d{2}[- _]"
            case FolderType.SUBCATEGORY:
                return r"^\d{2}\.\d{2}[- _]"
            case _:
                msg = f"Unknown folder type: {self}"
                raise ValueError(msg)


class ProjectType(str, Enum):
    """Enum for project types."""

    JD = "jd"
    FOLDER = "folder"


class Separator(Enum):
    """Define choices for separator transformation."""

    DASH = "-"
    IGNORE = "ignore"
    NONE = ""
    SPACE = " "
    UNDERSCORE = "_"
    PERIOD = "."


class TransformCase(str, Enum):
    """Define choices for case transformation."""

    CAMELCASE = "camelcase"
    IGNORE = "ignore"
    LOWER = "lower"
    SENTENCE = "sentence"
    TITLE = "title"
    UPPER = "upper"


class InsertLocation(str, Enum):
    """Define choices for inserting text."""

    AFTER = "after"
    BEFORE = "before"


class DateFirst(str, Enum):
    """Define choices for date region."""

    DAY = "day"
    MONTH = "month"
    YEAR = "year"
