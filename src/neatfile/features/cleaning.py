"""Filename cleaning feature module."""

import re
from datetime import datetime
from typing import assert_never

from datefind import find_dates
from nclutils import pp

from neatfile import settings
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


def _add_date_to_filename(file: File, new_date: str) -> None:
    """Add a formatted date to the filename stem using the configured separator and location.

    Args:
        file (File): The file object containing the filename and date to add.
        new_date (str): The formatted date to add to the filename.
    """
    sep = (
        file.guess_separator().value
        if settings.separator == Separator.IGNORE
        else settings.separator.value
    )

    match settings.insert_location:
        case InsertLocation.BEFORE:
            file.new_stem = f"{new_date}{sep}{file.new_stem}"
        case InsertLocation.AFTER:
            file.new_stem = f"{file.new_stem}{sep}{new_date}"
        case _:  # pragma: no cover
            assert_never(settings.insert_location)


def clean_filename(file: File) -> None:
    """Process and clean filenames according to configured settings.

    Apply a series of transformations to filenames including date formatting, word splitting, stopword removal, case transformation, and separator normalization.

    Args:
        file (File): The file object to process.
    """
    new_date = datetime.fromtimestamp(file.path.stat().st_ctime, tz=settings.tz).strftime(
        settings.date_format
    )
    for date in find_dates(
        text=settings.get("date", None) or file.stem,
        first=settings.date_first.value,
    ):
        new_date = date.date.strftime(settings.date_format)
        file.new_stem = re.sub(re.escape(date.match), "", file.new_stem)
        break

    if not settings.date_only:
        stem_tokens = tokenize_string(file.new_stem)
        pp.trace(f"CLEAN (tokenize): {stem_tokens}")

        stem_tokens = strip_special_chars(stem_tokens)
        pp.trace(f"CLEAN (strip special chars): {stem_tokens}")

        stem_tokens = split_camel_case(stem_tokens, settings.match_case_list)
        pp.trace(f"CLEAN (split camel case): {stem_tokens}")

        if settings.split_words:
            stem_tokens = split_camel_case(stem_tokens, settings.match_case_list)
            pp.trace(f"CLEAN (split words): {stem_tokens}")
        if settings.strip_stopwords:
            filtered_tokens = strip_stopwords(stem_tokens, settings.stopwords)
            # Keep original tokens if stripping stopwords would remove everything
            stem_tokens = filtered_tokens or stem_tokens
            pp.trace(f"CLEAN (strip stopwords): {stem_tokens}")

        stem_tokens = transform_case(stem_tokens, settings.transform_case)
        pp.trace(f"CLEAN (transform case): {stem_tokens}")

        stem_tokens = match_case(stem_tokens, settings.match_case_list)
        pp.trace(f"CLEAN (match case): {stem_tokens}")

        file.new_stem = f"{settings.separator.value if settings.separator != Separator.IGNORE else file.guess_separator().value}".join(
            stem_tokens
        )

    if new_date:
        _add_date_to_filename(file, new_date)
        pp.trace(f"CLEAN (add date): {file.new_stem}")

    if file.is_dotfile and not file.new_stem.startswith("."):
        file.new_stem = f".{file.new_stem}"
        pp.trace(f"CLEAN (add dotfile): {file.new_stem}")

    file.new_suffix = ".jpg" if file.suffix.lower() == ".jpeg" else file.suffix.lower()

    if file.name != file.new_name:
        pp.trace(f"CLEAN (final): {file.name} -> {file.new_name}")
    else:
        pp.trace(f"CLEAN (final): No changes to {file.name}")
