"""Tests for filename cleaning helpers."""

from pathlib import Path
from types import SimpleNamespace

from pytest_mock import MockerFixture

from neatfile.features.cleaning import _creation_timestamp


def test_creation_timestamp_prefers_birth_time(tmp_path: Path, mocker: MockerFixture) -> None:
    """Verify the file birth time is used when the platform reports one."""
    mocker.patch.object(
        Path,
        "stat",
        return_value=SimpleNamespace(st_birthtime=100.0, st_mtime=200.0, st_ctime=300.0),
    )

    assert _creation_timestamp(tmp_path / "file.txt") == 100.0


def test_creation_timestamp_falls_back_to_mtime(tmp_path: Path, mocker: MockerFixture) -> None:
    """Verify modification time is used when birth time is unavailable, never ctime."""
    mocker.patch.object(Path, "stat", return_value=SimpleNamespace(st_mtime=200.0, st_ctime=300.0))

    assert _creation_timestamp(tmp_path / "file.txt") == 200.0
