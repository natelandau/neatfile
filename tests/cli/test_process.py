"""Test process command."""

from datetime import UTC, datetime

import cappa
import pytest
from cappa.base import invoke

from neatfile.cli import NO_DATE_FORMAT_MESSAGE, NO_PROJECT_MESSAGE, NeatFile, configure_output

TODAY = datetime.now(tz=UTC).date().strftime("%Y-%m-%d")


@pytest.mark.parametrize(
    ("input_name", "extraargs", "setting_update", "msg"),
    [
        pytest.param(
            ".dotfile_test.txt",
            ["--project", "mock_jd_project"],
            {"ignore_dotfiles": True},
            "No files found",
            id="fail-no-files, ignore-dotfiles",
        ),
        pytest.param(
            "file.txt",
            ["--date-only"],
            {"date_format": ""},
            NO_DATE_FORMAT_MESSAGE,
            id="fail-no-date-format",
        ),
        pytest.param(
            "file.txt",
            [],
            {},
            NO_PROJECT_MESSAGE,
            id="fail-no-project",
        ),
    ],
)
def test_process_failure_states(
    create_file,
    write_user_config,
    input_name,
    setting_update,
    extraargs,
    msg,
    debug,
    capsys,
):
    """Verify process command handles failure states correctly."""
    # Given: A test file exists
    filename = create_file(input_name)

    # Given: Command arguments and settings are configured
    args = ["process", *extraargs, str(filename), "-vv"]
    write_user_config(setting_update)

    # When: Invoking the clean command
    with pytest.raises(cappa.Exit) as e:
        invoke(obj=NeatFile, argv=args, deps=[configure_output])

    # Then: Command output and exit code are verified
    _, stderr = capsys.readouterr()
    # debug(output, "output")

    assert e.value.code == 1
    if msg:
        assert msg in stderr


def test_process_command_match(tmp_path, create_file, capsys, mocker, debug):
    """Verify sorting files into project folder based on name matching."""
    # Given: Mock questionary select to return first option
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = 0

    # Given: A test file exists
    file = create_file("this is a foo $$$$ file.txt")

    # When: Running sort command
    args = ["process", str(file), "--project", "mock_jd_project", "-v", "--date-format", ""]
    # args = ["tree", "--project", "mock_jd_project", "-v"]
    with pytest.raises(cappa.Exit):
        invoke(obj=NeatFile, argv=args, deps=[configure_output])

    # Then: File is moved to matching folder
    output = capsys.readouterr().out
    assert "Found 5 possible folders" in output
    assert "this is a foo $$$$ file.txt -> 10-19 foo/foo-file.txt" in output
    assert not file.exists()
    assert (tmp_path / "project" / "10-19 foo" / "foo-file.txt").exists()
