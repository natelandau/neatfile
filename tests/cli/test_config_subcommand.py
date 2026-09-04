"""Tests for the CLI settings hook."""

import cappa
import pytest

from neatfile import settings
from neatfile.cli import NeatFile, config_subcommand


def test_cli_settings_only_carry_defined_options(create_file) -> None:
    """Verify the settings hook does not inject options that no command defines."""
    file = create_file("file.txt")

    with pytest.raises(cappa.Exit):
        cappa.invoke(
            obj=NeatFile,
            argv=["clean", "--date-format", "", str(file)],
            deps=[config_subcommand],
        )

    assert "full_tree" not in settings
