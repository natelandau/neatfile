"""Filename cleaning feature module."""

import re
from datetime import datetime
from pathlib import Path
from typing import assert_never

from datefind import FoundDate, find_dates
from nclutils import pp

from neatfile.config import Config
from neatfile.constants import SEPARATOR_CHARACTERS, InsertLocation, Separator
from neatfile.models import File
from neatfile.utils.strings import (
    guess_separator,
    join_tokens,
    match_case,
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


def _first_date(text: str, *, config: Config) -> FoundDate | None:
    """Return the first date in `text`, so callers can both use it and strip its text.

    Args:
        text (str): The text to search.
        config (Config): The settings that decide how ambiguous numeric dates are read.

    Returns:
        FoundDate | None: The first date found, or None when the text holds no date.
    """
    return next(iter(find_dates(text=text, first=config.date_first.value)), None)


def parse_date_option(text: str | None, *, config: Config) -> FoundDate | None:
    """Read the date from the `--date` option once per run, warning when it holds none.

    Args:
        text (str | None): The `--date` value, or None when the option was not given.
        config (Config): The settings that decide how ambiguous numeric dates are read.

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
    file: File, *, config: Config, filename_date: FoundDate | None, override_date: FoundDate | None
) -> str:
    """Return the date to add to the name, in the configured format.

    Prefer `override_date`, then the date in the filename, then the file's creation time.

    Args:
        file (File): The file whose creation time is the last resort.
        config (Config): The settings that hold the date format.
        filename_date (FoundDate | None): The first date in the filename, or None.
        override_date (FoundDate | None): The date from `--date`, or None.

    Returns:
        str: The formatted date, or an empty string when `date_format` is empty.
    """
    if not config.date_format:
        return ""

    chosen_date: FoundDate | None = override_date or filename_date
    if chosen_date is not None:
        return chosen_date.datetime.strftime(config.date_format)

    created: datetime = datetime.fromtimestamp(_creation_timestamp(file.path), tz=config.tz)
    return created.strftime(config.date_format)


def _clean_tokens(stem: str, *, config: Config) -> list[str]:
    """Split a stem into words and normalize them according to the settings.

    Args:
        stem (str): The stem to clean.
        config (Config): The settings that control each transformation.

    Returns:
        list[str]: The cleaned words, ready to join. Empty when nothing survives cleaning.
    """
    tokens: list[str] = tokenize_string(stem)
    pp.trace(f"CLEAN (tokenize): {tokens}")

    tokens = strip_special_chars(tokens)
    pp.trace(f"CLEAN (strip special chars): {tokens}")

    if config.split_words:
        tokens = split_camel_case(string_list=tokens, match_case_list=config.match_case_list)
        pp.trace(f"CLEAN (split words): {tokens}")

    if config.strip_stopwords:
        # Keep original tokens if stripping stopwords would remove everything
        tokens = strip_stopwords(tokens=tokens, stopwords=config.stopwords) or tokens
        pp.trace(f"CLEAN (strip stopwords): {tokens}")

    tokens = transform_case(tokens=tokens, case_style=config.transform_case)
    pp.trace(f"CLEAN (transform case): {tokens}")

    tokens = match_case(tokens=tokens, match_case_list=config.match_case_list)
    pp.trace(f"CLEAN (match case): {tokens}")

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


def clean_filename(
    file: File, *, config: Config, override_date: FoundDate | None, date_only: bool
) -> None:
    """Plan a cleaned name on `file` so the caller can preview and apply the rename.

    Set `file.new_stem` and `file.new_suffix` in place. Remove any date from the stem and add the
    chosen date back in the configured format. Unless `date_only` is set, normalize the words in
    between: strip special characters, split camelCase, drop stopwords, and transform and match
    case. Keep the original stem when cleaning would leave the name empty.

    Args:
        file (File): The file to plan a new name for. Mutated in place.
        config (Config): The settings that control each transformation.
        override_date (FoundDate | None): The date from `--date`, parsed with `parse_date_option`, or None to use the file's own date.
        date_only (bool): Add the date and make no other changes to the name.
    """
    # A dotfile's leading dot is neither a word separator nor part of the words, so set it aside
    # and restore it once the rest of the name is built
    name_body: str = file.stem.removeprefix(".") if file.is_dotfile else file.stem

    filename_date: FoundDate | None = _first_date(text=name_body, config=config)
    date_text: str = filename_date.match if filename_date else ""
    new_date: str = _format_date(
        file=file, config=config, filename_date=filename_date, override_date=override_date
    )

    # Guess before trimming the separators around the date, which are part of the name's style
    separator: str = (
        guess_separator(name_body.replace(date_text, "")).value
        if config.separator == Separator.IGNORE
        else config.separator.value
    )
    stem: str = _remove_date_text(stem=name_body, date_text=date_text) if date_text else name_body

    if not date_only:
        tokens: list[str] = _clean_tokens(stem=stem, config=config)
        stem = join_tokens(tokens=tokens, case_style=config.transform_case, separator=separator)

    if new_date:
        stem = _add_date(
            stem=stem,
            new_date=new_date,
            separator=separator,
            insert_location=config.insert_location,
        )
        pp.trace(f"CLEAN (add date): {stem}")

    if not stem:
        stem = file.stem
        pp.trace(f"CLEAN (empty name): keeping {file.stem}")
    elif file.is_dotfile:
        stem = f".{stem}"
        pp.trace(f"CLEAN (add dotfile): {stem}")

    file.new_stem = stem
    suffix: str = file.suffix.lower()
    file.new_suffix = ".jpg" if suffix == ".jpeg" else suffix

    if file.name != file.new_name:
        pp.trace(f"CLEAN (final): {file.name} -> {file.new_name}")
    else:
        pp.trace(f"CLEAN (final): No changes to {file.name}")
