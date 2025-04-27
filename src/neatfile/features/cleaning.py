"""Filename cleaning feature module."""

import re
from datetime import datetime, timezone
from typing import assert_never

from neatfile import settings
from neatfile.constants import InsertLocation, Separator
from neatfile.models import Date, File
from neatfile.utils import pp
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


def _find_and_format_date(file: File) -> str:
    """Search for a date in the filename, remove it, and store a reformatted version.

    Extract any date found in the filename's stem, remove the original date text, and store a reformatted version based on the configured date format. Uses file creation time as a fallback for relative dates.

    Args:
        file (File): The file object containing the filename to process.

    Returns:
        str: The reformatted date.
    """
    date_object = Date(
        string=file.new_stem,
        ctime=datetime.fromtimestamp(file.path.stat().st_ctime, tz=timezone.utc),
    )

    # If a date was found in the filename, remove it so we can format it and re-add it later
    if date_object.found_string:
        file.new_stem = re.sub(re.escape(date_object.found_string), "", file.new_stem)

    return date_object.reformatted_date


def clean_filename(file: File) -> None:
    """Process and clean filenames according to configured settings.

    Apply a series of transformations to filenames including date formatting, word splitting, stopword removal, case transformation, and separator normalization.

    Args:
        file (File): The file object to process.
    """
    if settings.get("date", None):
        new_date = Date(string=settings.date).reformatted_date
    else:
        new_date = _find_and_format_date(file) if settings.date_format else ""

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
