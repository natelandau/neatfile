"""Filename cleaning feature module."""

import re
from datetime import datetime
from pathlib import Path
from typing import assert_never

from datefind import find_dates
from nclutils import pp

from neatfile.config import Config
from neatfile.constants import InsertLocation, Separator
from neatfile.models import File
from neatfile.utils.strings import (
    match_case,
    split_camel_case,
    strip_special_chars,
    strip_stopwords,
    tokenize_string,
    transform_case,
)


def _add_date_to_filename(
    file: File, new_date: str, *, separator: Separator, insert_location: InsertLocation
) -> None:
    """Add a formatted date to the filename stem using the configured separator and location.

    Args:
        file (File): The file object containing the filename and date to add.
        new_date (str): The formatted date to add to the filename.
        separator (Separator): Separator between the date and the rest of the name.
        insert_location (InsertLocation): Whether the date goes before or after the name.
    """
    sep = file.guess_separator().value if separator == Separator.IGNORE else separator.value

    match insert_location:
        case InsertLocation.BEFORE:
            file.new_stem = f"{new_date}{sep}{file.new_stem}"
        case InsertLocation.AFTER:
            file.new_stem = f"{file.new_stem}{sep}{new_date}"
        case _:  # pragma: no cover
            assert_never(insert_location)


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


def clean_filename(file: File, *, config: Config, date: str | None, date_only: bool) -> None:
    """Process and clean filenames according to configured settings.

    Apply a series of transformations to filenames including date formatting, word splitting, stopword removal, case transformation, and separator normalization.

    Args:
        file (File): The file object to process.
        config (Config): The settings that control each transformation.
        date (str | None): Text to read the date from in place of the filename, or None to use the filename.
        date_only (bool): Add the date and make no other changes to the name.
    """
    new_date = datetime.fromtimestamp(_creation_timestamp(file.path), tz=config.tz).strftime(
        config.date_format
    )
    for found_date in find_dates(
        text=date or file.stem,
        first=config.date_first.value,
    ):
        new_date = found_date.datetime.strftime(config.date_format)
        file.new_stem = re.sub(re.escape(found_date.match), "", file.new_stem)
        break

    if not date_only:
        stem_tokens = tokenize_string(file.new_stem)
        pp.trace(f"CLEAN (tokenize): {stem_tokens}")

        stem_tokens = strip_special_chars(stem_tokens)
        pp.trace(f"CLEAN (strip special chars): {stem_tokens}")

        if config.split_words:
            stem_tokens = split_camel_case(stem_tokens, config.match_case_list)
            pp.trace(f"CLEAN (split words): {stem_tokens}")
        if config.strip_stopwords:
            filtered_tokens = strip_stopwords(stem_tokens, config.stopwords)
            # Keep original tokens if stripping stopwords would remove everything
            stem_tokens = filtered_tokens or stem_tokens
            pp.trace(f"CLEAN (strip stopwords): {stem_tokens}")

        stem_tokens = transform_case(stem_tokens, config.transform_case)
        pp.trace(f"CLEAN (transform case): {stem_tokens}")

        stem_tokens = match_case(stem_tokens, config.match_case_list)
        pp.trace(f"CLEAN (match case): {stem_tokens}")

        separator = (
            file.guess_separator() if config.separator == Separator.IGNORE else config.separator
        )
        file.new_stem = separator.value.join(stem_tokens)

    if new_date:
        _add_date_to_filename(
            file=file,
            new_date=new_date,
            separator=config.separator,
            insert_location=config.insert_location,
        )
        pp.trace(f"CLEAN (add date): {file.new_stem}")

    if file.is_dotfile and not file.new_stem.startswith("."):
        file.new_stem = f".{file.new_stem}"
        pp.trace(f"CLEAN (add dotfile): {file.new_stem}")

    file.new_suffix = ".jpg" if file.suffix.lower() == ".jpeg" else file.suffix.lower()

    if file.name != file.new_name:
        pp.trace(f"CLEAN (final): {file.name} -> {file.new_name}")
    else:
        pp.trace(f"CLEAN (final): No changes to {file.name}")
