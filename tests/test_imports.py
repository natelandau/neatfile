"""Tests for import-time cost of the CLI."""

import subprocess
import sys


def test_cli_import_does_not_load_numpy() -> None:
    """Verify importing the CLI leaves numpy unloaded so startup stays fast."""
    result = subprocess.run(
        [sys.executable, "-c", "import sys, neatfile.cli; print('numpy' in sys.modules)"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout == "False\n"
