"""Constants for the neatfile package."""

import os
from enum import Enum, StrEnum
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
VERSION = "5.0.1"
ALWAYS_IGNORE_FILES_REGEXES = [r"\.DS_Store$", r"\.neatfile$", r"\.stignore$", r"__pycache__"]
NEATFILE_NAME = ".neatfile"
NEATFILE_IGNORE_NAME = ".neatfileignore"
# Multi-part extensions kept whole so the stem excludes them. Matched case-insensitively.
COMPOUND_EXTENSIONS = (
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".tar.zst",
    ".tar.lz",
    ".tar.lzma",
    ".tar.z",
    ".d.ts",
    ".d.mts",
    ".d.cts",
    ".min.js",
    ".min.css",
    ".min.mjs",
    ".spec.ts",
    ".spec.js",
    ".spec.tsx",
    ".spec.jsx",
    ".test.ts",
    ".test.js",
    ".test.tsx",
    ".test.jsx",
    ".user.js",
    ".user.css",
)
# English stopword list from spaCy (MIT license), bundled so filename cleaning needs no model.
_CURLY_QUOTE_CLITICS: frozenset[str] = frozenset(
    {
        f"{quote}{suffix}"
        for quote in ("\u2018", "\u2019")
        for suffix in ("d", "ll", "m", "re", "s", "ve")
    }
    | {f"n{quote}t" for quote in ("\u2018", "\u2019")}
)
_ENGLISH_STOPWORDS_ASCII = """
'd 'll 'm 're 's 've a about above across after afterwards again against all almost alone along
already also although always am among amongst amount an and another any anyhow anyone anything
anyway anywhere are around as at back be became because become becomes becoming been before
beforehand behind being below beside besides between beyond both bottom but by ca call can
cannot could did do does doing done down due during each eight either eleven else elsewhere
empty enough even ever every everyone everything everywhere except few fifteen fifty first five
for former formerly forty four from front full further get give go had has have he hence her
here hereafter hereby herein hereupon hers herself him himself his how however hundred i if in
indeed into is it its itself just keep last latter latterly least less made make many may me
meanwhile might mine more moreover most mostly move much must my myself n't name namely neither
never nevertheless next nine no nobody none noone nor not nothing now nowhere of off often on
once one only onto or other others otherwise our ours ourselves out over own part per perhaps
please put quite rather re really regarding same say see seem seemed seeming seems serious
several she should show side since six sixty so some somehow someone something sometime
sometimes somewhere still such take ten than that the their them themselves then thence there
thereafter thereby therefore therein thereupon these they third this those though three through
throughout thru thus to together too top toward towards twelve twenty two under unless until up
upon us used using various very via was we well were what whatever when whence whenever where
whereafter whereas whereby wherein whereupon wherever whether which while whither who whoever
whole whom whose why will with within without would yet you your yours yourself yourselves
"""
ENGLISH_STOPWORDS: frozenset[str] = (
    frozenset(_ENGLISH_STOPWORDS_ASCII.split()) | _CURLY_QUOTE_CLITICS
)


class PrintLevel(Enum):
    """Define verbosity levels for console output.

    Use these levels to control the amount of information displayed to users. Higher levels include all information from lower levels plus additional details.
    """

    INFO = 0
    DEBUG = 1
    TRACE = 2


class FolderType(StrEnum):
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


class ProjectType(StrEnum):
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


class TransformCase(StrEnum):
    """Define choices for case transformation."""

    CAMELCASE = "camelcase"
    IGNORE = "ignore"
    LOWER = "lower"
    SENTENCE = "sentence"
    TITLE = "title"
    UPPER = "upper"


class InsertLocation(StrEnum):
    """Define choices for inserting text."""

    AFTER = "after"
    BEFORE = "before"


class DateFirst(StrEnum):
    """Define choices for date region."""

    DAY = "day"
    MONTH = "month"
    YEAR = "year"
