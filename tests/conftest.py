"""Shared fixtures for tests."""

import re
from collections.abc import Callable
from pathlib import Path

import pytest
import tomllib

from neatfile import settings
from neatfile.constants import DEFAULT_CONFIG_PATH, DateRegion
from neatfile.utils import console, pp


@pytest.fixture
def clean_stdout(capsys: pytest.CaptureFixture[str], monkeypatch) -> Callable[[], str]:
    r"""Return a function that cleans ANSI escape sequences from captured stdout.

    This fixture is useful for testing CLI output where ANSI color codes and other escape sequences need to be stripped to verify the actual text content. The returned callable captures stdout using pytest's capsys fixture and removes all ANSI escape sequences, making it easier to write assertions against the cleaned output.

    Args:
        capsys (pytest.CaptureFixture[str]): Pytest fixture that captures stdout/stderr streams

    Returns:
        Callable[[], str]: A function that when called returns the current stdout with all ANSI escape sequences removed

    Example:
        def test_cli_output(clean_stdout):
            print("\033[31mRed Text\033[0m")  # Colored output
            assert clean_stdout() == "Red Text"  # Test against clean text
    """
    # Set the terminal width to 180 columns to avoid unwanted line breaks
    monkeypatch.setenv("COLUMNS", "180")

    ansi_chars = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]")

    def _get_clean_stdout() -> str:
        return ansi_chars.sub("", capsys.readouterr().out)

    return _get_clean_stdout


@pytest.fixture
def debug() -> Callable[[str | Path, str, bool, int], bool]:
    """Create a debug printing function for test development.

    Return a function that prints formatted debug output with clear visual separation and optional breakpoints. Useful for inspecting variables, file contents, or directory structures during test development.

    Returns:
        Callable[[str | Path, str, bool, int], bool]: Debug printing function with parameters:
            - value: Data to debug print (string or Path)
            - label: Optional header text
            - breakpoint: Whether to pause execution after printing
            - width: Maximum output width in characters
    """

    def _debug_inner(
        value: str | Path,
        label: str = "",
        *,
        breakpoint: bool = False,
        width: int = 80,
    ) -> bool:
        """Print formatted debug information during test development.

        Format and display debug output with labeled headers and clear visual separation. Supports printing file contents, directory structures, and variable values with optional execution breakpoints.

        Args:
            value (str | Path): Value to debug print. For Path objects, prints directory tree
            label (str): Optional header text for context
            breakpoint (bool, optional): Pause execution after printing. Defaults to False
            width (int, optional): Maximum output width. Defaults to 80

        Returns:
            bool: True unless breakpoint is True, then raises pytest.fail()
        """
        console.rule(label or "")

        # If a directory is passed, print the contents
        if isinstance(value, Path) and value.is_dir():
            for p in value.rglob("*"):
                console.print(p, width=width)
        else:
            console.print(value, width=width)

        console.rule()

        if breakpoint:
            return pytest.fail("Breakpoint")

        return True

    return _debug_inner


@pytest.fixture(autouse=True)
def set_default_settings(tmp_path, mock_project, mocker):
    """Verify default settings are configured correctly for tests."""
    # Given: Mock config file paths to force using the default config
    mock_config = tmp_path / "config.toml"
    mock_dev = tmp_path / "dev.toml"
    mocker.patch("neatfile.config.USER_CONFIG_PATH", mock_config)
    mocker.patch("neatfile.config.DEV_CONFIG_PATH", mock_dev)

    # Given: Reset settings to defaults
    if settings.get("project"):
        settings.update({"project": {}})
    if settings.get("date"):
        settings.update({"date": None})
    if settings.get("date_region"):
        settings.update({"date_region": DateRegion.US})
    if settings.get("file_search_depth"):
        settings.update({"file_search_depth": 1})

    settings.update(tomllib.loads(DEFAULT_CONFIG_PATH.read_text()))

    # And: Configuring mock projects
    _, project_path = mock_project
    mock_project_config = {
        "mock_jd_project": {
            "path": project_path,
            "depth": 0,
            "type": "jd",
            "separator": "dash",
        },
        "mock_folder_project": {"path": project_path, "depth": 3, "type": "folder"},
    }
    settings.update({"projects": mock_project_config})

    # Lastly: Configure pretty printer
    pp.configure(debug=False, trace=False)


@pytest.fixture
def mock_project(tmp_path):
    """Fixture to create a mock project folder structure and original files which can be filed.

    Returns:
        tuple: (original_files_dir, project_root_dir)
    """
    # Mock project folder structure using animals as friendly keys for names
    # `koala` matches 2 folders
    # `fox` matches 1 folder
    # `cat` matches 1 folder
    # `dog` matches 1 folder
    # `bear` matches no folders
    dir_names = [
        ".dotfile_dir",
        "10-19 foo/11 bar/11.01 foo",
        "10-19 foo/11 bar/11.02 bar",
        "10-19 foo/11 bar/11.03 koala",
        "10-19 foo/12 baz/12.01 foo",
        "10-19 foo/12 baz/12.02 bar",
        "10-19 foo/12 baz/12.03 koala",
        "10-19 foo/12 baz/12.04 baz",
        "10-19 foo/12 baz/12.05 waldo",
        "20-29_bar/20_foo/20.01_foo_bar_baz",
        "20-29_bar/20_foo/20.02_bar",
        "20-29_bar/20_foo/20.03_waldo",
        "20-29_bar/20_foo/20.04 fox",
        "20-29_bar/20_foo/20.04 fox/some_dir",
        "20-29_bar/21_bar",
        "20-29_bar/22 cat",
        "30-39_baz",
        "40-49 dog",
        "foo/bar/foo",
        "foo/bar/bar",
        "foo/bar/baz",
        "foo/bar/qux",
    ]

    test_files = [
        "quick brown fox.txt",
        "lazy dog.txt",
        "cute fluffy cat.txt",
        "big orange bear.txt",
        # "cuddly gray koala.txt",
    ]

    project_path = Path(tmp_path / "project")
    project_path.mkdir(parents=True, exist_ok=True)

    original_files_path = Path(tmp_path / "originals")
    original_files_path.mkdir(parents=True, exist_ok=True)

    for d in dir_names:
        Path(project_path / d).mkdir(parents=True, exist_ok=True)

    for f in test_files:
        Path(original_files_path / f).touch()

    return original_files_path, project_path


@pytest.fixture
def create_dir(tmp_path):
    """Create a directory for testing."""  # noqa: DOC201

    def _inner(name: str, parent: Path | None = None):
        """Create a directory with the provided name and path.

        Args:
            name (str): The name of the directory to create.
            path (Path, optional): The path to create the directory in. Defaults to None.

        Returns:
            Path: The path to the created directory.
        """
        if not parent:
            dir_path = tmp_path / "project"
            dir_path.mkdir(parents=True, exist_ok=True)
            return dir_path

        dir_path = parent / name
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    return _inner


@pytest.fixture
def create_file(tmp_path):
    """Create a file for testing."""  # noqa: DOC201

    def _inner(name: str, path: str | None = None, content: str | None = None):
        """Create a file with the provided name and content.

        Args:
            name (str): The name of the file to create.
            path (str, optional): The path to create the file in. Defaults to None.
            content (str, optional): The content to write to the file. Defaults to None.

        Returns:
            Path: The path to the created file.
        """
        file_path = Path(tmp_path / path / name) if path else Path(tmp_path / name)

        if path:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        if content:
            file_path.write_text(content)
        else:
            file_path.touch()

        return file_path

    return _inner
