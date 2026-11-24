"""Tests for filename cleaning helpers."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from datefind import FoundDate
from pytest_mock import MockerFixture

from neatfile.config import Config
from neatfile.constants import InsertLocation, Separator, TransformCase
from neatfile.features.cleaning import (
    DATE_NOT_FOUND_MESSAGE,
    _creation_timestamp,
    clean_name,
    parse_date_option,
)
from neatfile.models import File


def _planned_name(
    name: str,
    *,
    config: Config,
    override_date: FoundDate | None = None,
    date_only: bool = False,
    fallback_date: Callable[[], datetime] | None = None,
) -> str:
    """Return the cleaned filename for `name`, split into stem and suffix the way neatfile does."""
    file = File(Path(name))
    cleaned = clean_name(
        stem=file.stem,
        suffix=file.suffix,
        config=config,
        override_date=override_date,
        date_only=date_only,
        fallback_date=fallback_date,
    )
    return f"{cleaned.stem}{cleaned.suffix}"


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
def test_clean_name(
    dated_config: Config,
    name: str,
    date: str | None,
    date_only: bool,
    settings: dict[str, object],
    expected: str,
) -> None:
    """Verify the planned name for edge-case filenames and date sources."""
    config = replace(dated_config, **settings)

    assert (
        _planned_name(
            name,
            config=config,
            override_date=parse_date_option(date, config=config),
            date_only=date_only,
        )
        == expected
    )


def test_parse_date_option_warns_when_value_has_no_date(
    dated_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify an unparsable `--date` value is reported rather than silently ignored."""
    assert parse_date_option("soon", config=dated_config) is None

    output = capsys.readouterr()
    assert DATE_NOT_FOUND_MESSAGE.format(value="soon") in output.out + output.err


@pytest.mark.parametrize(
    ("name", "settings", "expected"),
    [
        pytest.param(
            "Part Two First Draft.txt",
            {},
            "Part Two First Draft.txt",
            id="keeps-numbers-and-ordinals",
        ),
        pytest.param("The Report of the Board.txt", {}, "Report Board.txt", id="drops-filler"),
        pytest.param(
            "NOTES FOR THE IT TEAM.txt", {}, "NOTES IT TEAM.txt", id="all-caps-keeps-protected"
        ),
        pytest.param("fix it for us later.txt", {}, "fix later.txt", id="lowercase-it-us-removed"),
        pytest.param("Plan A.txt", {}, "Plan.txt", id="trailing-stopword-removed"),
        pytest.param(
            "Plan A.txt", {"match_case_list": ("A",)}, "Plan A.txt", id="match-case-list-protects"
        ),
        pytest.param(
            "final draft notes.txt",
            {"stopwords": ("draft",)},
            "final notes.txt",
            id="user-stopwords-added",
        ),
        pytest.param("the of.txt", {}, "the of.txt", id="all-stopwords-keeps-original"),
    ],
)
def test_clean_name_stopwords(
    default_config: Config,
    name: str,
    settings: dict[str, object],
    expected: str,
) -> None:
    """Verify filename cleaning removes only filler words and keeps protected words."""
    config = replace(
        default_config,
        date_format="",
        separator=Separator.SPACE,
        strip_stopwords=True,
        **settings,
    )

    assert _planned_name(name, config=config) == expected


def test_clean_name_uses_fallback_date_only_when_name_has_none(dated_config: Config) -> None:
    """Verify the fallback date names an undated file and never replaces a date in the name."""
    created = datetime(2020, 1, 2, tzinfo=UTC)

    assert _planned_name("notes.txt", config=dated_config, fallback_date=lambda: created) == (
        "2020-01-02_Notes.txt"
    )
    assert _planned_name("notes.txt", config=dated_config) == "Notes.txt"
    assert (
        _planned_name("notes 2024-05-06.txt", config=dated_config, fallback_date=lambda: created)
        == "2024-05-06 Notes.txt"
    )
