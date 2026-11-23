"""Tests for the CLI settings dependencies and the config command."""

from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

import pytest
from cappa.base import invoke
from pytest_mock import MockerFixture

from neatfile.cli import (
    CleanCommand,
    NeatFile,
    SortCommand,
    build_config,
    build_run_options,
    configure_output,
)
from neatfile.config import RunOptions


class CleanFlags(TypedDict, total=False):
    """Optional flags of the clean command that map to settings."""

    separator: str
    date_format: str
    overwrite: bool


@pytest.mark.parametrize(
    ("command_options", "expected_overrides"),
    [
        pytest.param({}, {}, id="no-flags"),
        pytest.param(
            {"separator": "UNDERSCORE", "date_format": "%Y", "overwrite": True},
            {"separator": "UNDERSCORE", "date_format": "%Y", "overwrite_existing": True},
            id="setting-flags",
        ),
    ],
)
def test_cli_settings_only_carry_defined_options(
    tmp_path: Path,
    mocker: MockerFixture,
    command_options: CleanFlags,
    expected_overrides: dict[str, object],
) -> None:
    """Verify only flags the user gave reach the loader, and run options hold only CLI values."""
    # Given: A clean command with some optional flags set
    load_config = mocker.patch("neatfile.cli.load_config")
    file = tmp_path / "file.txt"
    neatfile = NeatFile(command=CleanCommand(files=[file], **command_options))

    # When: Building the settings and run options for the command
    build_config(neatfile)
    options = build_run_options(neatfile)

    # Then: The loader receives exactly the given flags and the run options hold only the file
    assert load_config.call_args.kwargs["cli_overrides"] == expected_overrides
    assert options == RunOptions(files=(file,))


def test_cli_terms_override_only_when_given(tmp_path: Path, mocker: MockerFixture) -> None:
    """Verify --term values reach the loader as user_terms."""
    # Given: A sort command with one --term flag
    load_config = mocker.patch("neatfile.cli.load_config")
    neatfile = NeatFile(command=SortCommand(files=[tmp_path / "f.txt"], user_terms=("cat",)))

    # When: Building the settings
    build_config(neatfile)

    # Then: Only the terms are passed as an override
    assert load_config.call_args.kwargs["cli_overrides"] == {"user_terms": ("cat",)}


def test_config_command_shows_broken_config(
    write_user_config: Callable[[dict[str, object]], Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify the config command shows a user config file even when its values are invalid."""
    # Given: A user config file with a string where a boolean is expected
    write_user_config({"ignore_dotfiles": "false"})

    # When: Running the config command
    invoke(obj=NeatFile, argv=["config"], deps=[configure_output])

    # Then: The command succeeds and prints the file contents
    output = capsys.readouterr().out
    assert 'ignore_dotfiles = "false"' in output
