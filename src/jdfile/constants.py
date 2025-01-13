"""Constants for the jdfile package."""

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
CONFIG_PATH = CONFIG_DIR / "config.toml"

VERSION = "2.0.1"
ALWAYS_IGNORE_FILES = [".DS_Store", ".jdfile", ".stignore"]
SPINNER = "bouncingBall"


class FolderType(str, Enum):
    """Enum for folder types."""

    AREA = "area"  # Used by Johnny Decimal Folders
    CATEGORY = "category"  # Used by Johnny Decimal Folders
    SUBCATEGORY = "subcategory"  # Used by Johnny Decimal Folders
    OTHER = "other"  # Any non-JD folder


class ProjectType(str, Enum):
    """Enum for project types."""

    JD = "jd"
    FOLDER = "folder"


class Separator(str, Enum):
    """Define choices for separator transformation."""

    DASH = "-"
    IGNORE = "ignore"
    NONE = ""
    SPACE = " "
    UNDERSCORE = "_"


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
