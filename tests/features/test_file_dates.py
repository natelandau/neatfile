"""Tests for the dates neatfile reads from files themselves."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_mock import MockerFixture

from neatfile.constants import DateFallback
from neatfile.features.file_dates import filesystem_date


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
