"""Tests for the dates neatfile reads from files themselves."""

import io
import struct
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from pypdf import PdfWriter
from pytest_mock import MockerFixture

from neatfile.constants import DateFallback
from neatfile.features.file_dates import filesystem_date, read_metadata_date

TZ = ZoneInfo("America/New_York")


@pytest.mark.parametrize(
    ("stat_values", "fallback", "expected_timestamp"),
    [
        pytest.param(
            {"st_birthtime": 100.0, "st_mtime": 200.0, "st_ctime": 300.0},
            DateFallback.CREATED,
            100.0,
            id="created uses birth time",
        ),
        pytest.param(
            {"st_mtime": 200.0, "st_ctime": 300.0},
            DateFallback.CREATED,
            200.0,
            id="created without birth time uses mtime, never ctime",
        ),
        pytest.param(
            {"st_birthtime": 100.0, "st_mtime": 200.0, "st_ctime": 300.0},
            DateFallback.MODIFIED,
            200.0,
            id="modified uses mtime",
        ),
    ],
)
def test_filesystem_date(
    tmp_path: Path,
    mocker: MockerFixture,
    stat_values: dict[str, float],
    fallback: DateFallback,
    expected_timestamp: float,
) -> None:
    """Verify each fallback reads the matching file timestamp."""
    mocker.patch.object(Path, "stat", return_value=SimpleNamespace(**stat_values))

    assert filesystem_date(
        tmp_path / "file.txt", fallback=fallback, tz=UTC
    ) == datetime.fromtimestamp(expected_timestamp, tz=UTC)


def _jpeg_with_exif(date_text: str, offset_text: str | None = None) -> bytes:
    """Return a minimal JPEG whose Exif IFD holds DateTimeOriginal and, optionally, OffsetTimeOriginal."""
    entries: list[tuple[int, bytes]] = [(0x9003, date_text.encode() + b"\0")]
    if offset_text:
        entries.append((0x9011, offset_text.encode() + b"\0"))
    ifd0_offset = 8
    exif_ifd_offset = ifd0_offset + 2 + 12 + 4
    data_offset = exif_ifd_offset + 2 + 12 * len(entries) + 4
    exif_ifd = struct.pack("<H", len(entries))
    data = b""
    for tag, value in entries:
        exif_ifd += struct.pack("<HHII", tag, 2, len(value), data_offset + len(data))
        data += value
    exif_ifd += struct.pack("<I", 0)
    tiff = b"II*\0" + struct.pack("<I", ifd0_offset)
    tiff += (
        struct.pack("<H", 1)
        + struct.pack("<HHII", 0x8769, 4, 1, exif_ifd_offset)
        + struct.pack("<I", 0)
    )
    tiff += exif_ifd + data
    app1 = b"Exif\0\0" + tiff
    return b"\xff\xd8\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1 + b"\xff\xd9"


def _pdf_with_creation_date(creation_date: str, *, password: str | None = None) -> bytes:
    """Return a one-page PDF whose document info holds `creation_date`."""
    writer = PdfWriter()
    writer.add_blank_page(width=10, height=10)
    writer.add_metadata({"/CreationDate": creation_date})
    if password:
        writer.encrypt(user_password=password)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _zip_bytes(members: dict[str, str]) -> bytes:
    """Return a zip archive holding `members`, keyed by archive path."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        for name, text in members.items():
            archive.writestr(name, text)
    return buffer.getvalue()


def _office_with_created(created: str) -> bytes:
    """Return an Office-style zip whose core properties hold `created`."""
    core_xml = (
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
        ' xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>'
        "</cp:coreProperties>"
    )
    return _zip_bytes({"docProps/core.xml": core_xml})


@pytest.mark.parametrize(
    ("filename", "contents", "expected"),
    [
        pytest.param(
            "photo.jpg",
            _jpeg_with_exif("2023:09:04 12:34:56"),
            datetime(2023, 9, 4, 12, 34, 56, tzinfo=TZ),
            id="photo without offset read in tz",
        ),
        pytest.param(
            "photo.JPG",
            _jpeg_with_exif("2023:09:04 12:34:56", "+02:00"),
            datetime(2023, 9, 4, 6, 34, 56, tzinfo=TZ),
            id="photo offset converted to tz, uppercase suffix",
        ),
        pytest.param(
            "scan.PDF",
            _pdf_with_creation_date("D:20230904123456+02'00'"),
            datetime(2023, 9, 4, 6, 34, 56, tzinfo=TZ),
            id="pdf",
        ),
        pytest.param(
            "report.docx",
            _office_with_created("2023-09-04T12:34:56Z"),
            datetime(2023, 9, 4, 8, 34, 56, tzinfo=TZ),
            id="docx",
        ),
        pytest.param(
            "budget.xlsx",
            _office_with_created("2023-09-04T12:34:56Z"),
            datetime(2023, 9, 4, 8, 34, 56, tzinfo=TZ),
            id="xlsx",
        ),
    ],
)
def test_read_metadata_date_finds_date(
    tmp_path: Path, filename: str, contents: bytes, expected: datetime
) -> None:
    """Verify the creation date stored in each supported file type is read in the configured zone."""
    path = tmp_path / filename
    path.write_bytes(contents)

    assert read_metadata_date(path, tz=TZ) == expected


@pytest.mark.parametrize(
    ("filename", "contents"),
    [
        pytest.param("photo.jpg", _jpeg_with_exif("0000:00:00 00:00:00"), id="unset camera clock"),
        pytest.param("photo.jpg", b"not an image", id="corrupt photo"),
        pytest.param("scan.pdf", b"junk", id="corrupt pdf"),
        pytest.param(
            "scan.pdf",
            _pdf_with_creation_date("D:20230904123456", password="secret"),  # noqa: S106
            id="encrypted pdf",
        ),
        pytest.param(
            "report.docx",
            _zip_bytes({"word/document.xml": "<w/>"}),
            id="office zip without core.xml",
        ),
        pytest.param("report.pptx", b"junk", id="not a zip"),
        pytest.param("notes.txt", b"2023-09-04", id="unsupported type"),
    ],
)
def test_read_metadata_date_without_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], filename: str, contents: bytes
) -> None:
    """Verify a missing or unreadable metadata date gives None without printing library warnings."""
    path = tmp_path / filename
    path.write_bytes(contents)

    assert read_metadata_date(path, tz=TZ) is None
    assert capsys.readouterr().err == ""
