"""Shared fixtures for tests."""

import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest
from nclutils import pp

from neatfile import constants
from neatfile.config import Config, load_config

# Anchor the test model to the repo so pytest launched from any cwd reuses one download.
os.environ.setdefault(
    "NEATFILE_MODEL_DIR", str(Path(__file__).resolve().parent.parent / ".cache" / "models")
)


def _render_project_section(name: str, *, path: Path, settings: Mapping[str, object]) -> str:
    """Render a `[projects.NAME]` TOML table so tests can define projects in config files.

    Args:
        name: Project name used in the table header.
        path: Project folder.
        settings: Other keys for the table. JSON scalars and string lists are valid TOML values.

    Returns:
        str: The TOML table, ending with a blank line.
    """
    lines = [f"[projects.{name}]", f"path = {json.dumps(str(path))}"]
    lines.extend(f"{key} = {json.dumps(value)}" for key, value in settings.items())
    return "\n".join(lines) + "\n\n"


@pytest.fixture
def render_project_section() -> Callable[..., str]:
    """Return the helper that renders a `[projects.NAME]` TOML table."""
    return _render_project_section


@pytest.fixture(autouse=True)
def isolate_config(
    tmp_path: Path, mock_project: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point the config loader at temporary files that define the mock projects."""
    config_dir = tmp_path / "config_files"
    config_dir.mkdir()
    dev_config = config_dir / "dev.toml"
    monkeypatch.setattr(constants, "USER_CONFIG_PATH", config_dir / "config.toml")
    monkeypatch.setattr(constants, "DEV_CONFIG_PATH", dev_config)

    for variable in list(os.environ):
        if variable.startswith("NEATFILE_") and variable != "NEATFILE_MODEL_DIR":
            monkeypatch.delenv(variable)

    _, project_path = mock_project
    dev_config.write_text(
        _render_project_section(
            "mock_jd_project",
            path=project_path,
            settings={"type": "jd", "separator": "dash"},
        )
        + _render_project_section(
            "mock_folder_project", path=project_path, settings={"depth": 4, "type": "folder"}
        )
    )

    pp.configure(verbosity=0)


@pytest.fixture
def default_config() -> Config:
    """Return the settings built from the package default config file alone."""
    return load_config(config_paths=(constants.DEFAULT_CONFIG_PATH,), environ={})


@pytest.fixture
def write_user_config() -> Callable[[dict[str, object]], Path]:
    """Return a function that writes top-level settings to the temporary user config file."""

    def _write(values: dict[str, object]) -> Path:
        if none_keys := [key for key, value in values.items() if value is None]:
            msg = f"Config values for {none_keys} are None; TOML has no null, so give a value"
            raise TypeError(msg)
        # JSON scalars and string lists are valid TOML values
        lines = [f"{key} = {json.dumps(value)}" for key, value in values.items()]
        path = constants.USER_CONFIG_PATH
        path.write_text("\n".join(lines) + "\n")
        return path

    return _write


@pytest.fixture
def mock_project(tmp_path: Path) -> tuple[Path, Path]:
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
def create_dir(tmp_path: Path) -> Callable[[str, Path | None], Path]:
    """Create a directory for testing."""

    def _inner(name: str, parent: Path | None = None) -> Path:
        """Create a directory with the provided name and path.

        Args:
            name (str): The name of the directory to create.
            parent (Path, optional): The path to create the directory in. Defaults to None.

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
def create_file(tmp_path: Path) -> Callable[[str, str | None, str | None], Path]:
    """Create a file for testing."""

    def _inner(name: str, path: str | None = None, content: str | None = None) -> Path:
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


@pytest.fixture(autouse=True)
def isolate_state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the state folder at a temporary path so no test writes to the real one."""
    state_dir = tmp_path / "state"
    monkeypatch.setattr(constants, "STATE_DIR", state_dir)
    return state_dir
