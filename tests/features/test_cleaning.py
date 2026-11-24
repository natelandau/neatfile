"""Tests for filename cleaning helpers."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_mock import MockerFixture

from neatfile.config import Config
from neatfile.constants import InsertLocation, Separator, TransformCase
from neatfile.features.cleaning import (
    DATE_NOT_FOUND_MESSAGE,
    _creation_timestamp,
    clean_filename,
    parse_date_option,
)
from neatfile.models import File


@pytest.fixture
def dated_config(default_config: Config) -> Config:
    """Return settings that add dates in ISO format and title-case the words."""
    return replace(default_config, date_format="%Y-%m-%d", transform_case=TransformCase.TITLE)


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


@pytest.mark.parametrize(
    ("name", "date", "date_only", "settings", "expected"),
    [
        pytest.param(
            "2024-01-01.txt", None, False, {}, "2024-01-01.txt", id="date-only-name-before"
        ),
        pytest.param(
            "2024-01-01.txt",
            None,
            False,
            {"insert_location": InsertLocation.AFTER},
            "2024-01-01.txt",
            id="date-only-name-after",
        ),
        pytest.param(
            "___.txt",
            None,
            False,
            {"date_format": ""},
            "___.txt",
            id="keep-name-when-cleaning-empties-it",
        ),
        pytest.param(
            "report 2020-05-01.txt",
            "2023-03-03",
            False,
            {},
            "2023-03-03 Report.txt",
            id="date-option-replaces-filename-date",
        ),
        pytest.param(
            "report 2020-05-01.txt",
            "no date here",
            False,
            {},
            "2020-05-01 Report.txt",
            id="date-option-without-date-uses-filename-date",
        ),
        pytest.param(
            "my iphone case.txt",
            None,
            False,
            {
                "date_format": "",
                "transform_case": TransformCase.CAMELCASE,
                "match_case_list": ("iPhone",),
            },
            "iPhoneCase.txt",
            id="camelcase-keeps-matched-case",
        ),
        pytest.param(
            "big-file-report 2024-01-01.txt",
            None,
            False,
            {"transform_case": TransformCase.CAMELCASE, "separator": Separator.IGNORE},
            "2024-01-01-bigFileReport.txt",
            id="camelcase-date-uses-original-separator",
        ),
        pytest.param(
            "2024-01-01 notes.txt",
            None,
            True,
            {},
            "2024-01-01 notes.txt",
            id="date-only-mode-leading-date",
        ),
        pytest.param(
            "foo_2024-01-01_bar.txt",
            None,
            True,
            {"separator": Separator.IGNORE},
            "2024-01-01_foo_bar.txt",
            id="date-only-mode-middle-date",
        ),
        pytest.param(
            ".bashrc",
            "2024-01-01",
            False,
            {"separator": Separator.IGNORE},
            ".2024-01-01_Bashrc",
            id="dotfile-leading-dot-is-not-a-separator",
        ),
        pytest.param(
            ".notes_2024-01-01",
            None,
            True,
            {"separator": Separator.IGNORE},
            ".2024-01-01_notes",
            id="date-only-mode-dotfile",
        ),
    ],
)
def test_clean_filename(
    tmp_path: Path,
    dated_config: Config,
    name: str,
    date: str | None,
    date_only: bool,
    settings: dict[str, object],
    expected: str,
) -> None:
    """Verify the planned name for edge-case filenames and date sources."""
    path = tmp_path / name
    path.touch()
    file = File(path)
    config = replace(dated_config, **settings)

    clean_filename(
        file=file,
        config=config,
        override_date=parse_date_option(date, config=config),
        date_only=date_only,
    )

    assert file.new_name == expected


def test_parse_date_option_warns_when_value_has_no_date(
    dated_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify an unparsable `--date` value is reported rather than silently ignored."""
    assert parse_date_option("soon", config=dated_config) is None

    output = capsys.readouterr()
    assert DATE_NOT_FOUND_MESSAGE.format(value="soon") in output.out + output.err
