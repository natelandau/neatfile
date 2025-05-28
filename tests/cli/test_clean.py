"""Test the clean command."""

from datetime import datetime, timezone
from pathlib import Path

import cappa
import pytest

from neatfile import settings
from neatfile.cli import NeatFile, config_subcommand

TODAY = datetime.now(tz=timezone.utc).date().strftime("%Y-%m-%d")


@pytest.mark.parametrize(
    ("input_name", "output_name", "extraargs", "setting_update", "expected_output"),
    [
        pytest.param(
            "space separated words.txt",
            "",
            ["--date-format", ""],
            {},
            "No changes made",
            id="no-changes, ignore-case",
        ),
        pytest.param(
            "dot.separated.words.txt",
            f"{TODAY}-dot-separated-words.txt",
            ["--date-format", "%Y-%m-%d"],
            {"separator": "dash"},
            "",
            id="dash-separator, date-format",
        ),
        pytest.param(
            "dot.separated.words.txt",
            f"dot-separated-words-{TODAY}.txt",
            [],
            {"separator": "dash", "insert_location": "after", "date_format": "%Y-%m-%d"},
            "",
            id="dash-separator, keep-date, insert-after",
        ),
        pytest.param(
            "dot.separated.words.txt",
            "",
            ["--dry-run"],
            {"separator": "dash", "date_format": "%Y-%m-%d"},
            f"dot.separated.words.txt -> {TODAY}-dot-separated-words.txt",
            id="dash-separator, keep-date, dry-run",
        ),
        pytest.param(
            "the $#@BAR(#FOO)*&^.txt",
            "BAR.FOO.txt",
            ["--date-format", ""],
            {"separator": "period"},
            "$#@BAR(#FOO)*&^.txt -> BAR.FOO.txt",
            id="special-characters, strip-stopwords",
        ),
        pytest.param(
            "the $#@BAR(#FOO)*&^.txt",
            f"{TODAY} the $#@BAR(#FOO)*&^.txt",
            ["--date-only"],
            {"separator": "ignore", "strip_stopwords": True, "date_format": "%Y-%m-%d"},
            f"the $#@BAR(#FOO)*&^.txt -> {TODAY} the $#@BAR(#FOO)*&^.txt",
            id="date-only, ignore-separator",
        ),
        pytest.param(
            ".dotfile_test.txt",
            "",
            ["--date-format", ""],
            {"ignore_dotfiles": False},
            "No changes made",
            id="pass-dotfiles",
        ),
        pytest.param(
            "the file.txt",
            "",
            ["--date-format", ""],
            {"strip_stopwords": False},
            "No changes",
            id="pass-stopwords",
        ),
        pytest.param(
            "FooBar.txt",
            "Foo_Bar.txt",
            ["--date-format", ""],
            {"split_words": True},
            "FooBar.txt -> Foo_Bar.txt",
            id="split-words",
        ),
        pytest.param(
            "Foo&Bar.txt",
            "FOO_BAR.txt",
            ["--date-format", "", "--case", "upper"],
            {},
            "Foo&Bar.txt -> FOO_BAR.txt",
            id="cli-transform-case",
        ),
        pytest.param(
            "Foo Bar.txt",
            "Foo.Bar.txt",
            ["--date-format", "", "--separator", "PERIOD"],
            {},
            "Foo Bar.txt -> Foo.Bar.txt",
            id="cli-separator",
        ),
        pytest.param(
            "2025-04-21 Foo Bar.txt",
            "20250421 Foo Bar.txt",
            ["--date-format", "%Y%m%d"],
            {},
            "2025-04-21 Foo Bar.txt -> 20250421 Foo Bar.txt",
            id="cli-date-format",
        ),
        pytest.param(
            "Foo Bar.txt",
            "20240329 Foo Bar.txt",
            ["--date", "2024-03-29", "--date-format", "%Y%m%d"],
            {},
            "Foo Bar.txt -> 20240329 Foo Bar.txt",
            id="cli-date",
        ),
        pytest.param(
            "040325 Foo Bar.txt",
            "2025-03-04 Foo Bar.txt",
            ["-vv"],
            {"date_first": "day", "date_format": "%Y-%m-%d"},
            "040325 Foo Bar.txt -> 2025-03-04 Foo Bar.txt",
            id="eu-ambiguous",
        ),
        pytest.param(
            "040325 Foo Bar.txt",
            "2025-04-03 Foo Bar.txt",
            ["-vv"],
            {"date_first": "month", "date_format": "%Y-%m-%d"},
            "040325 Foo Bar.txt -> 2025-04-03 Foo Bar.txt",
            id="us-ambiguous",
        ),
        pytest.param(
            "040325 Foo Bar.txt",
            "2004-03-25 Foo Bar.txt",
            ["-vv"],
            {"date_first": "year", "date_format": "%Y-%m-%d"},
            "040325 Foo Bar.txt -> 2004-03-25 Foo Bar.txt",
            id="jp-ambiguous",
        ),
    ],
)
def test_clean_single_file(
    create_file,
    input_name,
    output_name,
    setting_update,
    extraargs,
    expected_output,
    debug,
    clean_stdout,
):
    """Verify clean command processes single files according to settings."""
    # Given: A test file exists
    filename = create_file(input_name)

    # Given: Command arguments and settings are configured
    args = ["clean", *extraargs, str(filename)]
    settings.update(setting_update)

    # When: Invoking the clean command
    with pytest.raises(cappa.Exit) as e:
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Command output and file changes are verified
    output = clean_stdout()
    # debug(output, "output")

    assert e.value.code == 0
    if expected_output:
        assert expected_output in output
    if output_name:
        assert not filename.exists()
        assert Path(filename.parent, output_name).exists()
    else:
        assert filename.exists()


@pytest.mark.parametrize(
    ("input_name", "extraargs", "setting_update", "msg"),
    [
        pytest.param(
            ".dotfile_test.txt",
            [],
            {"ignore_dotfiles": True},
            "No files found",
            id="fail-no-files, ignore-dotfiles",
        ),
        pytest.param(
            "file.txt",
            ["--date-only"],
            {"date_format": ""},
            "date_format is not specified",
            id="fail-no-date-format",
        ),
        pytest.param(
            "file.txt",
            ["--sep", "asdfsdf"],
            {},
            "",
            id="fail-invalid-cli-separator",
        ),
        pytest.param(
            "file.txt",
            ["--case", "asdfsdf"],
            {},
            "",
            id="fail-invalid-cli-case",
        ),
    ],
)
def test_clean_failure_states(
    create_file,
    input_name,
    setting_update,
    extraargs,
    msg,
    debug,
    clean_stdout,
):
    """Verify clean command handles failure states correctly."""
    # Given: A test file exists
    filename = create_file(input_name)

    # Given: Command arguments and settings are configured
    args = ["clean", *extraargs, str(filename)]
    settings.update(setting_update)
    # debug(settings.as_dict(), "settings")

    # When: Invoking the clean command
    with pytest.raises(cappa.Exit) as e:
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Command output and exit code are verified
    output = clean_stdout()
    # debug(output, "output")

    assert e.value.code > 0
    if msg:
        assert msg in output


def test_clean_multiple_files(create_file, clean_stdout, debug):
    """Verify clean command processes multiple files correctly."""
    # Given: Multiple test files exist
    filenames = [
        ".dotfile_test.txt",
        f"{TODAY}-date.txt",
        "New File.txt",
    ]
    files = [str(create_file(f)) for f in filenames]

    # Given: Command arguments and settings are configured
    args = ["clean", "-v", *files]
    settings.update({"separator": "dash", "date_format": "%Y-%m-%d"})

    # When: Invoking the clean command
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Command output is verified
    output = clean_stdout()
    # debug(output, "output")

    assert "Ignored:" in output
    assert f"{TODAY}-date.txt -> No changes" in output
    assert f"New File.txt -> {TODAY}-New-File.txt" in output


def test_overwrite_file(create_file, clean_stdout, debug):
    """Verify clean command overwrites existing files when --overwrite flag is used."""
    # Given: Two test files exist - one to clean and one to be overwritten
    new = create_file("file#$%.txt", content="foo bar baz")
    original = create_file("file.txt", content="to be overwritten")

    # Given: Command arguments configured with overwrite flag
    args = ["clean", "-v", "--date-format", "", "--overwrite", str(new)]

    # When: Invoking the clean command
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Command output and file changes are verified
    output = clean_stdout()
    # debug(output, "output")

    assert "file#$%.txt -> file.txt" in output
    assert not new.exists()
    assert original.read_text() == "foo bar baz"


def test_view_diff_table_confirm_changes(create_file, clean_stdout, mocker, debug):
    """Verify confirmation table displays and applies changes when user confirms."""
    # Given: Mock user confirmation to return True
    mocker.patch("neatfile.commands.Confirm.ask", return_value=True)

    # Given: A test file exists with special characters
    original = create_file("file#$%.txt")

    # Given: Command arguments include confirm flag
    args = ["clean", "-v", "--date-format", "", "--confirm", str(original)]

    # When: Invoking the clean command
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Confirmation table and changes are displayed and applied
    output = clean_stdout()
    # debug(output, "output")

    assert "Pending changes for 1 of 1 files" in output
    assert "#   Original Name   New Name      Diff" in output
    assert "1   file#$%.txt     file.txt      file#$%.txt" in output
    assert "file#$%.txt -> file.txt" in output
    assert not original.exists()
    assert Path(original.parent, "file.txt").exists()


def test_view_diff_table_not_confirm_changes(create_file, clean_stdout, mocker, debug):
    """Verify confirmation table displays but no changes applied when user declines."""
    # Given: Mock user confirmation to return False
    mocker.patch("neatfile.commands.Confirm.ask", return_value=False)

    # Given: A test file exists with special characters
    original = create_file("file#$%.txt")

    # Given: Command arguments include confirm flag
    args = ["clean", "-v", "--date-format", "", "--confirm", str(original)]

    # When: Invoking the clean command
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Confirmation table displayed but no changes applied
    output = clean_stdout()

    assert "Pending changes for 1 of 1 files" in output
    assert "#   Original Name   New Name      Diff" in output
    assert "1   file#$%.txt     file.txt      file#$%.txt" in output
    assert "Changes not applied" in output
    assert original.exists()
    assert not Path(original.parent, "file.txt").exists()


def test_unique_filename_first(create_file, clean_stdout, tmp_path, debug):
    """Verify unique filename command works."""
    # Given: A test file exists
    original = create_file("file.txt")
    second = create_file("the file.txt")

    # Given: Command arguments include unique flag
    args = ["clean", "-v", "--date-format", "", str(second)]

    # When: Invoking the clean command
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Command output is verified
    output = clean_stdout()

    # find the backup file
    backup_file = None
    for file in tmp_path.iterdir():
        if file.name.endswith(".bak"):
            backup_file = file
            break

    assert backup_file is not None
    assert backup_file.exists()
    assert "file.txt -> file.txt" in output
    assert original.exists()
    assert not second.exists()


def test_unique_filename_directory(create_file, tmp_path, clean_stdout, debug):
    """Verify unique filename command works."""
    # Given: A test file exists
    directory = tmp_path / "directory"
    directory.mkdir()
    second = create_file("the directory")

    # Given: Command arguments include unique flag
    args = ["clean", "-v", "--date-format", "", str(second)]

    # When: Invoking the clean command
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # find the backup directory
    backup_dir = None
    for path in tmp_path.iterdir():
        if path.name.endswith(".bak"):
            backup_dir = path
            break

    # Then: Command output is verified
    output = clean_stdout()
    assert "directory -> directory" in output
    assert backup_dir.exists()
    assert backup_dir.is_dir()
    assert directory.exists()
    assert directory.is_file()
    assert not second.exists()
