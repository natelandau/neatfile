"""Dates read from a file itself, for naming files whose names hold no date."""

import logging
import struct
import zipfile
import zlib
from collections.abc import Callable
from datetime import datetime, tzinfo
from pathlib import Path
from typing import assert_never
from xml.etree import ElementTree as ET

import exifread
from exifread.core.exceptions import ExifError
from nclutils import pp
from pypdf import PdfReader
from pypdf.errors import DependencyError, PyPdfError

from neatfile.constants import DateFallback
from neatfile.utils.paths import display_path

# Both libraries print warnings to stderr for malformed files; neatfile reports those itself at
# debug level, so keep the libraries quiet
for _library_logger_name in ("exifread", "pypdf"):
    _library_logger = logging.getLogger(_library_logger_name)
    _library_logger.addHandler(logging.NullHandler())
    _library_logger.setLevel(logging.CRITICAL)

_EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"
_EXIF_DATE_TAGS = (
    ("EXIF DateTimeOriginal", "EXIF OffsetTimeOriginal"),
    ("EXIF DateTimeDigitized", "EXIF OffsetTimeDigitized"),
)
_OFFICE_CORE_PROPERTIES = "docProps/core.xml"
_OFFICE_CREATED_TAG = "{http://purl.org/dc/terms/}created"


def filesystem_date(path: Path, *, fallback: DateFallback, tz: tzinfo) -> datetime:
    """Return the file timestamp the user chose to date files that hold no other date.

    `CREATED` uses the birth time, which only some platforms report, and falls back to the
    modification time. ctime is never used because on Unix it is the inode change time and moves
    on every chmod or rename.

    Args:
        path (Path): The file to inspect.
        fallback (DateFallback): Which timestamp to read.
        tz (tzinfo): The time zone to express the date in.

    Returns:
        datetime: The chosen timestamp in `tz`.
    """
    stat = path.stat()
    match fallback:
        case DateFallback.CREATED:
            timestamp: float = getattr(stat, "st_birthtime", stat.st_mtime)
        case DateFallback.MODIFIED:
            timestamp = stat.st_mtime
        case _:
            assert_never(fallback)
    return datetime.fromtimestamp(timestamp, tz=tz)


def _parse_exif_date(tags: dict[str, object], date_tag: str, offset_tag: str) -> datetime | None:
    """Return the date in one EXIF date tag, with its offset when that tag parses.

    Args:
        tags (dict[str, object]): The tags exifread found.
        date_tag (str): The date tag to read.
        offset_tag (str): The tag holding that date's UTC offset.

    Returns:
        datetime | None: The date, or None when the tag is missing or malformed.
    """
    if date_tag not in tags:
        return None
    try:
        taken = datetime.strptime(str(tags[date_tag]).strip(), _EXIF_DATE_FORMAT)  # noqa: DTZ007
    except ValueError:
        return None
    # A malformed offset keeps the date, which is then read in the configured zone
    try:
        offset = datetime.strptime(str(tags.get(offset_tag, "")).strip(), "%z").tzinfo
    except ValueError:
        return taken
    return taken.replace(tzinfo=offset)


def _read_photo_date(path: Path) -> datetime | None:
    """Return the date a photo was taken, from the first EXIF date tag that parses.

    Args:
        path (Path): The photo to read.

    Returns:
        datetime | None: The capture date, with its offset when the photo records one.
    """
    with path.open("rb") as handle:
        tags = exifread.process_file(handle, details=False)
    return next(
        (
            taken
            for date_tag, offset_tag in _EXIF_DATE_TAGS
            if (taken := _parse_exif_date(tags, date_tag, offset_tag)) is not None
        ),
        None,
    )


def _read_pdf_date(path: Path) -> datetime | None:
    """Return a PDF's creation date from its document info, else from its XMP metadata.

    Args:
        path (Path): The PDF to read.

    Returns:
        datetime | None: The creation date, or None when the PDF records none.
    """
    # Passing a handle lets pypdf seek; given a path, it reads the whole file into memory
    with path.open("rb") as handle:
        reader = PdfReader(handle, strict=False)
        if reader.metadata is not None and reader.metadata.creation_date is not None:
            return reader.metadata.creation_date
        if reader.xmp_metadata is not None:
            return reader.xmp_metadata.xmp_create_date
    return None


def _read_office_date(path: Path) -> datetime | None:
    """Return the creation date stored in a Word, Excel, or PowerPoint file's core properties.

    Args:
        path (Path): The Office file to read.

    Returns:
        datetime | None: The creation date, or None when the file records none.
    """
    with zipfile.ZipFile(path) as archive:
        core_properties = ET.fromstring(archive.read(_OFFICE_CORE_PROPERTIES))  # noqa: S314
    created = core_properties.find(_OFFICE_CREATED_TAG)
    if created is None or not created.text:
        return None
    return datetime.fromisoformat(created.text.strip())


# The parsers read untrusted bytes and raise many unrelated errors on truncated, malformed, or
# encrypted files. Each is a missing date, never a reason to stop the run.
_UNREADABLE_METADATA_ERRORS: tuple[type[Exception], ...] = (
    AttributeError,
    DependencyError,
    EOFError,
    ET.ParseError,
    ExifError,
    IndexError,
    KeyError,
    NotImplementedError,
    OSError,
    OverflowError,
    PyPdfError,
    RecursionError,
    RuntimeError,
    TypeError,
    ValueError,
    struct.error,
    zipfile.BadZipFile,
    zlib.error,
)


_PHOTO_SUFFIXES = [
    ".arw",
    ".cr2",
    ".dng",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".nef",
    ".orf",
    ".png",
    ".rw2",
    ".tif",
    ".tiff",
    ".webp",
]
_METADATA_READERS: dict[str, Callable[[Path], datetime | None]] = {
    **dict.fromkeys(_PHOTO_SUFFIXES, _read_photo_date),
    ".pdf": _read_pdf_date,
    ".docx": _read_office_date,
    ".pptx": _read_office_date,
    ".xlsx": _read_office_date,
}


def read_metadata_date(path: Path, *, tz: tzinfo) -> datetime | None:
    """Return the creation date stored inside a photo, PDF, or Office file.

    Call this to date a file whose name holds no date. A date stored in the file is usually closer
    to the truth than the filesystem dates, which change when a file is downloaded or copied.

    Args:
        path (Path): The file to read.
        tz (tzinfo): The time zone to express the date in, and to read a date without an offset in.

    Returns:
        datetime | None: The stored date in `tz`, or None when the file type holds no date or the
            date cannot be read.
    """
    reader = _METADATA_READERS.get(path.suffix.lower())
    if reader is None:
        return None

    try:
        found = reader(path)
        if found is None:
            return None
        if found.tzinfo is None:
            return found.replace(tzinfo=tz)
        return found.astimezone(tz)
    except _UNREADABLE_METADATA_ERRORS as e:
        pp.debug(f"No metadata date in `{display_path(path)}`: {type(e).__name__}: {e}")
        return None


def fallback_file_date(path: Path, *, fallback: DateFallback, tz: tzinfo) -> datetime:
    """Return the date for a file whose name holds none: its metadata date, else a file timestamp.

    Args:
        path (Path): The file to date.
        fallback (DateFallback): Which file timestamp to use when the metadata holds no date.
        tz (tzinfo): The time zone to express the date in.

    Returns:
        datetime: The metadata date, else the chosen file timestamp, in `tz`.
    """
    return read_metadata_date(path, tz=tz) or filesystem_date(path, fallback=fallback, tz=tz)
