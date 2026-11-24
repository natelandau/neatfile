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
    MAX_FILENAME_BYTES,
    NAME_TOO_LONG_MESSAGE,
    _creation_timestamp,
    _truncate_to_bytes,
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
            "John's report 2024-01-01.txt",
            None,
            False,
            {},
            "2024-01-01 Johns Report.txt",
            id="possessive-stays-one-word",
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
        pytest.param(
            "040325 foo bar.txt",
            None,
            False,
            {"separator": Separator.SPACE},
            "040325 Foo Bar.txt",
            id="short-digit-run-not-a-date-by-default",
        ),
        pytest.param(
            "march 2025 statement.txt",
            None,
            False,
            {"separator": Separator.SPACE},
            "2025-03 Statement.txt",
            id="month-precision-short-form",
        ),
        pytest.param(
            "Q3 2024 report.txt",
            None,
            False,
            {"separator": Separator.SPACE},
            "2024-Q3 Report.txt",
            id="quarter-precision-short-form",
        ),
        pytest.param(
            "report.txt",
            "march 2025",
            False,
            {"separator": Separator.SPACE},
            "2025-03 Report.txt",
            id="date-option-month-precision-short-form",
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


@pytest.mark.parametrize(
    ("name", "date_only", "expected"),
    [
        pytest.param("con.txt", False, "Con_.txt", id="reserved-device-name"),
        pytest.param("Com1.backup.txt", True, "Com1_.backup.txt", id="reserved-before-first-dot"),
        pytest.param("nul", False, "Nul_", id="reserved-without-suffix"),
        pytest.param("com¹.txt", True, "com¹_.txt", id="reserved-superscript-port"),
        pytest.param("CONOUT$.log", True, "CONOUT$_.log", id="reserved-console-buffer"),
        pytest.param("console.txt", False, "Console.txt", id="longer-word-not-reserved"),
        pytest.param("2024-01-01 con.txt", False, "2024-01-01 Con.txt", id="dated-not-reserved"),
        pytest.param("notes. ", True, "notes", id="trailing-dot-and-space-without-suffix"),
        pytest.param("Meeting: Q4?.txt", True, "Meeting Q4.txt", id="invalid-characters-removed"),
    ],
)
def test_clean_name_is_valid_on_windows(
    dated_config: Config, name: str, date_only: bool, expected: str
) -> None:
    """Verify a planned name avoids the characters, names, and endings Windows refuses."""
    config: Config = replace(dated_config, separator=Separator.SPACE)

    assert _planned_name(name, config=config, date_only=date_only) == expected


@pytest.mark.parametrize(
    ("word", "date_only", "last_word"),
    [
        pytest.param("word", False, "Word", id="ascii-words"),
        pytest.param("wörd", False, "Wörd", id="multibyte-words"),
        pytest.param("word", True, "word", id="date-only-mode"),
    ],
)
def test_clean_name_fits_filename_byte_limit(
    dated_config: Config, word: str, date_only: bool, last_word: str
) -> None:
    """Verify a long name is cut to the byte limit at a word, keeping its date and extension."""
    config: Config = replace(dated_config, separator=Separator.UNDERSCORE)
    name: str = "_".join([word] * 100) + "_2024-01-01.pdf"

    planned: str = _planned_name(name, config=config, date_only=date_only)

    assert len(planned.encode()) <= MAX_FILENAME_BYTES
    assert planned.startswith("2024-01-01_")
    assert planned.endswith(f"_{last_word}.pdf")


def test_clean_name_keeps_name_when_date_and_extension_do_not_fit(
    dated_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify a name whose date and extension exceed the byte limit is left as it is."""
    name: str = "2024-01-01 abc." + "x" * 230

    assert _planned_name(name, config=dated_config) == name
    output = capsys.readouterr()
    assert NAME_TOO_LONG_MESSAGE.format(name=name, max_bytes=MAX_FILENAME_BYTES) in (
        output.out + output.err
    )


@pytest.mark.parametrize(
    ("text", "max_bytes", "expected"),
    [
        pytest.param("aaa_bbb_ccc", 7, "aaa_bbb", id="cut-lands-at-word-end"),
        pytest.param("aaa_bbb_ccc", 9, "aaa_bbb", id="cut-inside-word"),
        pytest.param("FirstSecondThird", 13, "FirstSecond", id="camel-case-words"),
        pytest.param("aaa-bbb ccc_ddd", 13, "aaa-bbb ccc", id="mixed-separators"),
        pytest.param("abcdefghij", 4, "abcd", id="single-long-word"),
    ],
)
def test_truncate_to_bytes_keeps_whole_words(text: str, max_bytes: int, expected: str) -> None:
    """Verify a shortened name ends on the last whole word that fits."""
    assert _truncate_to_bytes(text=text, max_bytes=max_bytes) == expected


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
        pytest.param(
            "don't open notes.txt",
            {"stopwords": ("don't",)},
            "open notes.txt",
            id="user-stopword-with-apostrophe",
        ),
        pytest.param(
            "mcdonald's menu.txt",
            {"match_case_list": ("McDonald's",), "split_words": True},
            "McDonalds menu.txt",
            id="match-case-entry-with-apostrophe",
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
    # A short digit date that `date_format` itself writes still reads as the name's date
    short_format_config = replace(dated_config, date_format="%m%d%y")
    assert (
        _planned_name("050624 notes.txt", config=short_format_config, fallback_date=lambda: created)
        == "050624 Notes.txt"
    )
