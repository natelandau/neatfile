"""Tests for the dates neatfile reads from files themselves."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from pypdf.errors import DependencyError
from pytest_mock import MockerFixture

from neatfile.constants import DateFallback
from neatfile.features.file_dates import filesystem_date, read_metadata_date
from tests.metadata_files import (
    jpeg_with_exif,
    office_with_created,
    pdf_with_creation_date,
    zip_bytes,
)

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


@pytest.mark.parametrize(
    ("filename", "contents", "expected"),
    [
        pytest.param(
            "photo.jpg",
            jpeg_with_exif("2023:09:04 12:34:56"),
            datetime(2023, 9, 4, 12, 34, 56, tzinfo=TZ),
            id="photo without offset read in tz",
        ),
        pytest.param(
            "photo.JPG",
            jpeg_with_exif("2023:09:04 12:34:56", "+02:00"),
            datetime(2023, 9, 4, 6, 34, 56, tzinfo=TZ),
            id="photo offset converted to tz, uppercase suffix",
        ),
        pytest.param(
            "scan.PDF",
            pdf_with_creation_date("D:20230904123456+02'00'"),
            datetime(2023, 9, 4, 6, 34, 56, tzinfo=TZ),
            id="pdf",
        ),
        pytest.param(
            "report.docx",
            office_with_created("2023-09-04T12:34:56Z"),
            datetime(2023, 9, 4, 8, 34, 56, tzinfo=TZ),
            id="docx",
        ),
        pytest.param(
            "budget.xlsx",
            office_with_created("2023-09-04T12:34:56Z"),
            datetime(2023, 9, 4, 8, 34, 56, tzinfo=TZ),
            id="xlsx",
        ),
        pytest.param(
            "photo.jpg",
            jpeg_with_exif("0000:00:00 00:00:00", digitized_text="2023:09:04 12:34:56"),
            datetime(2023, 9, 4, 12, 34, 56, tzinfo=TZ),
            id="unset original falls through to digitized",
        ),
        pytest.param(
            "photo.jpg",
            jpeg_with_exif("2023:09:04 12:34:56", "      "),
            datetime(2023, 9, 4, 12, 34, 56, tzinfo=TZ),
            id="blank offset keeps the date in tz",
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
        pytest.param("photo.jpg", jpeg_with_exif("0000:00:00 00:00:00"), id="unset camera clock"),
        pytest.param("photo.jpg", b"not an image", id="corrupt photo"),
        pytest.param("scan.pdf", b"junk", id="corrupt pdf"),
        pytest.param(
            "scan.pdf",
            pdf_with_creation_date("D:20230904123456", password="secret"),  # noqa: S106
            id="encrypted pdf",
        ),
        pytest.param(
            "report.docx",
            zip_bytes({"word/document.xml": "<w/>"}),
            id="office zip without core.xml",
        ),
        pytest.param("report.pptx", b"junk", id="not a zip"),
        pytest.param("notes.txt", b"2023-09-04", id="unsupported type"),
        pytest.param("photo.jpg", b"\xff\xd8\xff", id="truncated photo"),
        pytest.param(
            "scan.pdf",
            pdf_with_creation_date("D:00010101000000+05'00'"),
            id="pdf date out of range after conversion",
        ),
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


def test_read_metadata_date_pdf_needing_missing_decryption_library(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Verify an AES-encrypted PDF, which pypdf cannot open without `cryptography`, gives None."""
    path = tmp_path / "statement.pdf"
    path.write_bytes(pdf_with_creation_date("D:20230904123456"))
    mocker.patch(
        "pypdf.PdfReader",
        side_effect=DependencyError("cryptography>=3.1 is required for AES algorithm"),
    )

    assert read_metadata_date(path, tz=TZ) is None
