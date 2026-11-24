"""Filename cleaning feature module."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, tzinfo
from pathlib import Path
from typing import assert_never

from datefind import FoundDate, find_date
from nclutils import pp

from neatfile.config import Config
from neatfile.constants import (
    FILENAME_STOPWORDS,
    PROTECTED_CAPITALIZED_WORDS,
    SEPARATOR_CHARACTERS,
    InsertLocation,
    Separator,
)
from neatfile.utils.strings import (
    guess_separator,
    join_tokens,
    match_case,
    remove_inner_apostrophes,
    split_camel_case,
    strip_special_chars,
    strip_stopwords,
    tokenize_string,
    transform_case,
)

DATE_NOT_FOUND_MESSAGE = (
    "No date found in `--date` value `{value}`. Using the date in the filename, or the file's "
    "creation date when the filename has none."
)

_SEPARATOR_RUN = f"[{re.escape(''.join(SEPARATOR_CHARACTERS))}]*"
_SHORT_DIGIT_RUN = re.compile(r"\d{4,7}")
# Two-digit month and day give the longest output of formats such as `%m%d%y`
_SAMPLE_DATE = datetime(2000, 12, 31)  # noqa: DTZ001

# ext4 and most other Linux filesystems cap a name at 255 bytes, the tightest common limit. A
# backup of a replaced file appends `.<23-character id>.bak` (28 bytes) to its name, and that name
# must fit too.
MAX_FILENAME_BYTES = 255 - 28
NAME_TOO_LONG_MESSAGE = (
    "Keeping `{name}`: its date and extension alone are longer than {max_bytes} bytes."
)
# Windows refuses these characters anywhere in a name. Normal cleaning already drops them, but
# `--date-only` keeps the original words.
_WINDOWS_INVALID_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Windows refuses these names in any letter case, even with an extension such as `con.txt`
_WINDOWS_RESERVED_NAMES: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"{device}{number}" for device in ("COM", "LPT") for number in "0123456789¹²³"}
)


def _reads_short_digit_dates(config: Config) -> bool:
    """Decide whether runs of 4 to 7 digits count as dates.

    A `date_format` such as `%m%d%y` writes such a run, and a renamed file must still read as
    dated, or the next run adds a second date in front of it.

    Args:
        config (Config): The settings that hold `short_digit_dates` and `date_format`.

    Returns:
        bool: True when `short_digit_dates` is on or `date_format` writes a run of 4 to 7 digits.
    """
    if config.short_digit_dates:
        return True
    return _SHORT_DIGIT_RUN.fullmatch(_SAMPLE_DATE.strftime(config.date_format)) is not None


def _first_date(text: str, *, config: Config) -> FoundDate | None:
    """Return the first date in `text`, so callers can both use it and strip its text.

    Args:
        text (str): The text to search.
        config (Config): The settings that decide how numeric dates are read and the time zone.

    Returns:
        FoundDate | None: The first date found, or None when the text holds no date.
    """
    return find_date(
        text=text,
        first=config.date_first.value,
        tz=config.tz,
        short_digit_dates=_reads_short_digit_dates(config),
    )


def parse_date_option(text: str | None, *, config: Config) -> FoundDate | None:
    """Read the date from the `--date` option once per run, warning when it holds none.

    Args:
        text (str | None): The `--date` value, or None when the option was not given.
        config (Config): The settings that decide how numeric dates are read and the time zone.

    Returns:
        FoundDate | None: The date to use for every file, or None to use each file's own date.
    """
    if text is None:
        return None

    found_date: FoundDate | None = _first_date(text=text, config=config)
    if found_date is None:
        pp.warning(DATE_NOT_FOUND_MESSAGE.format(value=text))
    return found_date


def _creation_timestamp(path: Path) -> float:
    """Return the best available creation time for a file.

    Birth time is only reported on some platforms. Modification time is the fallback because
    ctime on Unix is the inode change time and moves on every chmod or rename.

    Args:
        path (Path): The file to inspect.

    Returns:
        float: Seconds since the epoch.
    """
    stat = path.stat()
    return getattr(stat, "st_birthtime", stat.st_mtime)


def file_creation_date(path: Path, *, tz: tzinfo) -> datetime:
    """Return when a file was created, for naming files whose names hold no date.

    Args:
        path (Path): The file to inspect.
        tz (tzinfo): The time zone to express the date in.

    Returns:
        datetime: The birth time where the platform reports one, else the modification time.
    """
    return datetime.fromtimestamp(_creation_timestamp(path), tz=tz)


def _remove_date_text(stem: str, date_text: str) -> str:
    """Remove every copy of `date_text` from `stem` along with the separators around it.

    A date in the middle of the stem leaves one separator behind so the words on either side stay
    apart.

    Args:
        stem (str): The stem to edit.
        date_text (str): The date as it appears in the stem.

    Returns:
        str: The stem without the date.
    """

    def _replacement(match: re.Match[str]) -> str:
        at_edge: bool = match.start() == 0 or match.end() == len(stem)
        separators: str = match.group("before") + match.group("after")
        return "" if at_edge else separators[:1]

    pattern: str = f"(?P<before>{_SEPARATOR_RUN}){re.escape(date_text)}(?P<after>{_SEPARATOR_RUN})"
    return re.sub(pattern=pattern, repl=_replacement, string=stem)


def _format_date(
    *,
    config: Config,
    filename_date: FoundDate | None,
    override_date: FoundDate | None,
    fallback_date: Callable[[], datetime] | None,
) -> str:
    """Return the date to add to the name, in the configured format.

    Prefer `override_date`, then the date in the filename, then `fallback_date`. A found date
    that names a period longer than a day, such as `March 2025` or `Q3 2024`, keeps that period
    in a short form (`2025-03`, `2024-Q3`) so the name never gains a day the source did not state.

    Args:
        config (Config): The settings that hold the date format.
        filename_date (FoundDate | None): The first date in the filename, or None.
        override_date (FoundDate | None): The date from `--date`, or None.
        fallback_date (Callable[[], datetime] | None): Returns the date to use when no other date
            is known, called only then. None adds no date in that case.

    Returns:
        str: The formatted date, or an empty string when `date_format` is empty or no date is known.
    """
    if not config.date_format:
        return ""

    chosen_date: FoundDate | None = override_date or filename_date
    if chosen_date is not None:
        if chosen_date.precision == "day":
            return chosen_date.datetime.strftime(config.date_format)
        return chosen_date.value

    if fallback_date is None:
        return ""

    return fallback_date().strftime(config.date_format)


def _filename_stopwords(config: Config) -> frozenset[str]:
    """Return the words to remove from filenames, honoring the user's additions and protections.

    Args:
        config (Config): The settings that hold the extra stopwords and `match_case_list`.

    Returns:
        frozenset[str]: Lowercase stopwords: the built-in filler words plus `stopwords`, minus any
            word in `match_case_list`.
    """
    # Filename tokens never hold inner apostrophes, so "don't" must become "dont" to match
    added: set[str] = {remove_inner_apostrophes(word.lower()) for word in config.stopwords}
    protected: set[str] = {
        remove_inner_apostrophes(word.lower()) for word in config.match_case_list
    }
    return frozenset((FILENAME_STOPWORDS | added) - protected)


def _clean_tokens(stem: str, *, config: Config) -> list[str]:
    """Split a stem into words and normalize them according to the settings.

    Args:
        stem (str): The stem to clean.
        config (Config): The settings that control each transformation.

    Returns:
        list[str]: The cleaned words, ready to join. Empty when nothing survives cleaning.
    """
    # Tokens never keep an inner apostrophe, so entries such as "McDonald's" must drop theirs to match
    match_case_list: tuple[str, ...] = tuple(
        remove_inner_apostrophes(word) for word in config.match_case_list
    )
    tokens: list[str] = tokenize_string(remove_inner_apostrophes(stem))
    pp.debug(f"CLEAN (tokenize): {tokens}")

    tokens = strip_special_chars(tokens)
    pp.debug(f"CLEAN (strip special chars): {tokens}")

    if config.split_words:
        tokens = split_camel_case(string_list=tokens, match_case_list=match_case_list)
        pp.debug(f"CLEAN (split words): {tokens}")

    if config.strip_stopwords:
        # Keep original tokens if stripping stopwords would remove everything
        tokens = (
            strip_stopwords(
                tokens=tokens,
                stopwords=_filename_stopwords(config),
                protected_words=PROTECTED_CAPITALIZED_WORDS,
            )
            or tokens
        )
        pp.debug(f"CLEAN (strip stopwords): {tokens}")

    tokens = transform_case(tokens=tokens, case_style=config.transform_case)
    pp.debug(f"CLEAN (transform case): {tokens}")

    tokens = match_case(tokens=tokens, match_case_list=match_case_list)
    pp.debug(f"CLEAN (match case): {tokens}")

    return tokens


def _add_date(stem: str, *, new_date: str, separator: str, insert_location: InsertLocation) -> str:
    """Return `stem` with `new_date` added before or after it.

    Args:
        stem (str): The cleaned stem.
        new_date (str): The formatted date to add.
        separator (str): Text between the date and the stem.
        insert_location (InsertLocation): Whether the date goes before or after the stem.

    Returns:
        str: The stem with the date, or the date alone when the stem is empty.
    """
    if not stem:
        return new_date

    match insert_location:
        case InsertLocation.BEFORE:
            return f"{new_date}{separator}{stem}"
        case InsertLocation.AFTER:
            return f"{stem}{separator}{new_date}"
        case _:  # pragma: no cover
            assert_never(insert_location)


def _starts_word(text: str, index: int) -> bool:
    """Report whether a word ends right before `index`, so a cut there keeps whole words.

    Args:
        text (str): The text to inspect.
        index (int): A position in `text`, greater than 0 and less than its length.

    Returns:
        bool: True when `text[index]` is a separator or the capital that starts a camelCase word.
    """
    character: str = text[index]
    return character in SEPARATOR_CHARACTERS or (character.isupper() and text[index - 1].islower())


def _truncate_to_bytes(text: str, *, max_bytes: int) -> str:
    """Shorten `text` to at most `max_bytes` of UTF-8, ending on a whole word when possible.

    Words end at any separator character or at a camelCase capital, so names joined without a
    separator, and `--date-only` names that mix separators, also keep whole words.

    Args:
        text (str): The text to shorten.
        max_bytes (int): The largest allowed UTF-8 length.

    Returns:
        str: `text` unchanged when it fits, else its longest prefix that fits, cut back to the last
            whole word and stripped of trailing separators.
    """
    encoded: bytes = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text

    # Dropping a partial trailing byte sequence keeps the cut on a character boundary
    truncated: str = encoded[: max(max_bytes, 0)].decode(encoding="utf-8", errors="ignore")
    word_end: int | None = next(
        (index for index in range(len(truncated), 0, -1) if _starts_word(text=text, index=index)),
        None,
    )
    if word_end is not None:
        truncated = text[:word_end]
    return truncated.rstrip("".join(SEPARATOR_CHARACTERS))


def _make_portable(stem: str, suffix: str) -> str:
    """Change `stem` so the full name is valid on Windows as well as macOS and Linux.

    Windows refuses characters such as `:` and `?`, drops a trailing dot or space from a name, and
    refuses device names such as `CON`, so a name that works on one system can break a synced or
    shared folder.

    Args:
        stem (str): The planned stem.
        suffix (str): The planned suffix.

    Returns:
        str: The stem without characters Windows refuses, without trailing dots or spaces when
            the name has no suffix, and with an underscore after a reserved device name.
    """
    stem = _WINDOWS_INVALID_CHARACTERS.sub("", stem) or stem
    if not suffix:
        stem = stem.rstrip(". ") or stem

    # Windows reads the text before the first dot, ignoring trailing spaces, as the device name
    base_name, dot, rest = stem.partition(".")
    if base_name.rstrip(" ").upper() in _WINDOWS_RESERVED_NAMES:
        return f"{base_name}_{dot}{rest}"
    return stem


@dataclass(frozen=True)
class CleanedName:
    """Hold the stem and suffix that cleaning planned for a filename."""

    stem: str
    suffix: str


def clean_name(
    stem: str,
    suffix: str,
    *,
    config: Config,
    override_date: FoundDate | None,
    date_only: bool,
    fallback_date: Callable[[], datetime] | None = None,
) -> CleanedName:
    """Plan a cleaned filename without touching the disk, so callers can preview or apply it.

    Remove any date from the stem and add the chosen date back in the configured format. Unless
    `date_only` is set, normalize the words in between: strip special characters, split camelCase,
    drop stopwords, and transform and match case. Keep the original stem when cleaning would leave
    the name empty. Keep the name valid on Windows, macOS, and Linux: shorten the words to fit
    `MAX_FILENAME_BYTES`, drop characters and trailing dots or spaces that Windows refuses, and
    add an underscore to a reserved Windows device name such as `CON`. Keep the original name,
    with a warning, when the date and extension alone do not fit.

    Args:
        stem (str): The current stem, with any leading dot of a dotfile.
        suffix (str): The current suffix.
        config (Config): The settings that control each transformation.
        override_date (FoundDate | None): The date from `--date`, parsed with `parse_date_option`, or None to use the name's own date.
        date_only (bool): Add the date and make no other changes to the name beyond keeping it valid on every system.
        fallback_date (Callable[[], datetime] | None, optional): Returns the date to use when neither `override_date` nor the name holds one, such as the file's creation date. Defaults to None, which adds no date in that case.

    Returns:
        CleanedName: The planned stem and suffix.
    """
    is_dotfile: bool = stem.startswith(".")
    # A dotfile's leading dot is neither a word separator nor part of the words, so set it aside
    # and restore it once the rest of the name is built
    name_body: str = stem.removeprefix(".") if is_dotfile else stem

    filename_date: FoundDate | None = _first_date(text=name_body, config=config)
    date_text: str = filename_date.match if filename_date else ""
    new_date: str = _format_date(
        config=config,
        filename_date=filename_date,
        override_date=override_date,
        fallback_date=fallback_date,
    )

    # Guess before trimming the separators around the date, which are part of the name's style
    separator: str = (
        guess_separator(name_body.replace(date_text, "")).value
        if config.separator == Separator.IGNORE
        else config.separator.value
    )
    new_stem: str = (
        _remove_date_text(stem=name_body, date_text=date_text) if date_text else name_body
    )

    if not date_only:
        tokens: list[str] = _clean_tokens(stem=new_stem, config=config)
        new_stem = join_tokens(tokens=tokens, case_style=config.transform_case, separator=separator)

    lowered_suffix: str = suffix.lower()
    new_suffix: str = ".jpg" if lowered_suffix == ".jpeg" else lowered_suffix

    # Shorten only the words, so the date and the extension always survive. The extra byte leaves
    # room for the underscore that `_make_portable` adds after a device name.
    reserved_bytes: int = len(f"{new_suffix}{new_date}{separator if new_date else ''}".encode())
    new_stem = _truncate_to_bytes(
        text=new_stem, max_bytes=MAX_FILENAME_BYTES - reserved_bytes - int(is_dotfile) - 1
    )

    if new_date:
        new_stem = _add_date(
            stem=new_stem,
            new_date=new_date,
            separator=separator,
            insert_location=config.insert_location,
        )
        pp.debug(f"CLEAN (add date): {new_stem}")

    if not new_stem:
        new_stem = stem
        pp.debug(f"CLEAN (empty name): keeping {stem}")
    elif is_dotfile:
        new_stem = f".{new_stem}"
        pp.debug(f"CLEAN (add dotfile): {new_stem}")

    new_stem = _make_portable(stem=new_stem, suffix=new_suffix)

    name: str = f"{stem}{suffix}"
    new_name: str = f"{new_stem}{new_suffix}"
    if len(new_name.encode()) > MAX_FILENAME_BYTES:
        pp.warning(NAME_TOO_LONG_MESSAGE.format(name=name, max_bytes=MAX_FILENAME_BYTES))
        return CleanedName(stem=stem, suffix=suffix)

    if name != new_name:
        pp.debug(f"CLEAN (final): {name} -> {new_name}")
    else:
        pp.debug(f"CLEAN (final): No changes to {name}")

    return CleanedName(stem=new_stem, suffix=new_suffix)
