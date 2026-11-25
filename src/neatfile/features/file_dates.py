"""Dates read from a file itself, for naming files whose names hold no date."""

import logging
import struct
import zipfile
import zlib
from collections.abc import Callable
from datetime import UTC, datetime, tzinfo
from pathlib import Path
from typing import TYPE_CHECKING, assert_never
from xml.etree import ElementTree as ET

from nclutils import pp

from neatfile.constants import DateFallback
from neatfile.utils.paths import display_path

if TYPE_CHECKING:
    from pypdf import DocumentInformation

# Both libraries log warnings for malformed files, which Python prints to stderr when nothing
# handles them; neatfile reports unreadable metadata itself at debug level
for _library_logger_name in ("exifread", "pypdf"):
    logging.getLogger(_library_logger_name).setLevel(logging.CRITICAL)

_EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"
_EXIF_DATE_TAGS = (
    ("EXIF DateTimeOriginal", "EXIF OffsetTimeOriginal"),
    ("EXIF DateTimeDigitized", "EXIF OffsetTimeDigitized"),
)
_OFFICE_CORE_PROPERTIES = "docProps/core.xml"
_OFFICE_CREATED_TAG = "{http://purl.org/dc/terms/}created"
# Real core properties are a few kilobytes; the cap stops a zip bomb from exhausting memory
_MAX_OFFICE_CORE_PROPERTIES_BYTES = 1024 * 1024

# Errors the parsers raise on truncated, malformed, or encrypted files. Each means the file has no
# usable date, never a reason to stop the run.
_PHOTO_PARSER_ERRORS: tuple[type[Exception], ...] = (
    AttributeError,
    EOFError,
    IndexError,
    KeyError,
    NotImplementedError,  # A HEIC box that runs to the end of the file
    OSError,
    TypeError,
    ValueError,
    struct.error,
)
_PDF_PARSER_ERRORS: tuple[type[Exception], ...] = (
    AttributeError,
    IndexError,
    KeyError,
    NotImplementedError,  # A stream compressed with a filter pypdf does not support
    OSError,
    RecursionError,
    TypeError,
    ValueError,
    struct.error,
    zlib.error,
)
_OFFICE_PARSER_ERRORS: tuple[type[Exception], ...] = (
    EOFError,
    ET.ParseError,
    KeyError,
    LookupError,  # An XML declaration naming an unknown encoding
    OSError,
    RuntimeError,  # Unsupported compression or an encrypted archive member
    ValueError,
    zipfile.BadZipFile,
    zlib.error,
)


class _UnreadableMetadataError(Exception):
    """Signal that a file's metadata cannot be parsed, carrying the parser's reason."""

    def __init__(self, cause: Exception) -> None:
        super().__init__(f"{type(cause).__name__}: {cause}")


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
    try:
        taken = datetime.strptime(str(tags.get(date_tag, "")).strip(), _EXIF_DATE_FORMAT)  # noqa: DTZ007
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

    Raises:
        _UnreadableMetadataError: If the photo's EXIF data cannot be parsed.
    """
    # Imported lazily so runs that never read a photo do not pay for loading the parser
    import exifread  # noqa: PLC0415
    from exifread.core.exceptions import ExifError  # noqa: PLC0415

    try:
        with path.open("rb") as handle:
            tags = exifread.process_file(handle, details=False)
    except (*_PHOTO_PARSER_ERRORS, ExifError) as e:
        raise _UnreadableMetadataError(e) from e

    return next(
        (
            taken
            for date_tag, offset_tag in _EXIF_DATE_TAGS
            if (taken := _parse_exif_date(tags=tags, date_tag=date_tag, offset_tag=offset_tag))
            is not None
        ),
        None,
    )


def _read_pdf_info_date(info: "DocumentInformation | None", *, path: Path) -> datetime | None:
    """Return the creation date in a PDF's document info, so a malformed one still lets XMP answer.

    Args:
        info (DocumentInformation | None): The PDF's document info, or None when it has none.
        path (Path): The PDF, named in the debug message for a malformed date.

    Returns:
        datetime | None: The creation date, or None when it is missing or malformed.
    """
    if info is None:
        return None
    try:
        return info.creation_date
    except ValueError as e:
        pp.debug(f"Malformed document info creation date in `{display_path(path)}`: {e}")
        return None


def _read_pdf_date(path: Path) -> datetime | None:
    """Return a PDF's creation date from its document info, else from its XMP metadata.

    Args:
        path (Path): The PDF to read.

    Returns:
        datetime | None: The creation date, or None when the PDF records none.

    Raises:
        _UnreadableMetadataError: If the PDF cannot be parsed or decrypted.
    """
    # Imported lazily so runs that never read a PDF do not pay for loading the parser
    from pypdf import PdfReader  # noqa: PLC0415
    from pypdf.errors import DependencyError, PyPdfError  # noqa: PLC0415

    try:
        # Passing a handle lets pypdf seek; given a path, it reads the whole file into memory
        with path.open("rb") as handle:
            reader = PdfReader(handle, strict=False)
            info_date = _read_pdf_info_date(reader.metadata, path=path)
            if info_date is not None:
                return info_date
            xmp = reader.xmp_metadata
            if xmp is None or xmp.xmp_create_date is None:
                return None
            # pypdf converts XMP dates to UTC and drops the zone
            return xmp.xmp_create_date.replace(tzinfo=UTC)
    except (*_PDF_PARSER_ERRORS, DependencyError, PyPdfError) as e:
        raise _UnreadableMetadataError(e) from e


def _read_office_core_properties(archive: zipfile.ZipFile) -> bytes:
    """Return an Office archive's core properties XML without inflating more than the size cap.

    Args:
        archive (zipfile.ZipFile): The open Office archive.

    Returns:
        bytes: The core properties XML.

    Raises:
        ValueError: If the core properties exceed `_MAX_OFFICE_CORE_PROPERTIES_BYTES`.
    """
    with archive.open(_OFFICE_CORE_PROPERTIES) as member:
        core_xml = member.read(_MAX_OFFICE_CORE_PROPERTIES_BYTES + 1)
    if len(core_xml) > _MAX_OFFICE_CORE_PROPERTIES_BYTES:
        msg = (
            f"`{_OFFICE_CORE_PROPERTIES}` is larger than the "
            f"{_MAX_OFFICE_CORE_PROPERTIES_BYTES}-byte limit for core properties"
        )
        raise ValueError(msg)
    return core_xml


def _read_office_date(path: Path) -> datetime | None:
    """Return the creation date stored in a Word, Excel, or PowerPoint file's core properties.

    Args:
        path (Path): The Office file to read.

    Returns:
        datetime | None: The creation date, or None when the file records none.

    Raises:
        _UnreadableMetadataError: If the file is not a readable Office archive or holds a malformed
            date.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            core_properties = ET.fromstring(_read_office_core_properties(archive))  # noqa: S314
        created = core_properties.find(_OFFICE_CREATED_TAG)
        if created is None or not created.text:
            return None
        return datetime.fromisoformat(created.text.strip())
    except _OFFICE_PARSER_ERRORS as e:
        raise _UnreadableMetadataError(e) from e


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
_OFFICE_SUFFIXES = (".docx", ".pptx", ".xlsx")
_METADATA_READERS: dict[str, Callable[[Path], datetime | None]] = {
    **dict.fromkeys(_PHOTO_SUFFIXES, _read_photo_date),
    **dict.fromkeys(_OFFICE_SUFFIXES, _read_office_date),
    ".pdf": _read_pdf_date,
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
    except _UnreadableMetadataError as e:
        pp.debug(f"No metadata date in `{display_path(path)}`: {e}")
        return None

    if found is None:
        return None
    if found.tzinfo is None:
        return found.replace(tzinfo=tz)
    try:
        return found.astimezone(tz)
    except OverflowError as e:
        pp.debug(f"Metadata date in `{display_path(path)}` is out of range: {found!r}: {e}")
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
