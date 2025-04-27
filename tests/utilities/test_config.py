"""Test the config module."""

from typing import Any

import cappa
import pytest
from dynaconf import Dynaconf

from neatfile.config import SettingsManager
from neatfile.constants import InsertLocation, Separator, TransformCase
from neatfile.models import Project


@pytest.fixture
def reset_settings_manager():
    """Reset SettingsManager singleton between tests."""
    # Given: Reset the singleton instance
    SettingsManager._instance = None
    yield
    # Cleanup after test
    SettingsManager._instance = None


def test_initialize_creates_singleton(reset_settings_manager, debug) -> None:
    """Verify SettingsManager creates a singleton instance with default values."""
    settings = SettingsManager.initialize()

    # Then: Instance is created with correct type
    assert isinstance(settings, Dynaconf)
    assert SettingsManager._instance is settings

    # debug(settings.to_dict())

    # And: Default values are set correctly
    assert not settings.date_format
    assert settings.ignore_dotfiles is True
    assert settings.ignore_file_regex == "^$"
    assert settings.ignored_files == []
    assert settings.insert_location == InsertLocation.BEFORE
    assert settings.match_case_list == []
    assert settings.overwrite_existing is False
    assert settings.separator == Separator.IGNORE
    assert settings.split_words is False
    assert settings.stopwords == []
    assert settings.strip_stopwords is True
    assert settings.transform_case == TransformCase.IGNORE


def test_initialize_returns_existing_instance(reset_settings_manager) -> None:
    """Verify SettingsManager returns existing instance on subsequent calls."""
    # Given: An existing settings instance
    first_instance = SettingsManager.initialize()

    # When: Initializing settings again
    second_instance = SettingsManager.initialize()

    # Then: Same instance is returned
    assert first_instance is second_instance
    assert SettingsManager._instance is first_instance


def test_apply_project_settings_updates_settings(
    tmp_path, reset_settings_manager, mocker, debug
) -> None:
    """Verify applying project settings updates global settings correctly."""
    # Given: A test project directory and configuration
    project_name = "test_project"
    project_path = tmp_path / "test_project"
    project_path.mkdir(parents=True, exist_ok=True)
    mock_dev = tmp_path / "dev.toml"
    mock_dev.touch()
    with mock_dev.open("w") as f:
        f.write(f"""\
[projects]
[projects.{project_name}]
name = "{project_name}"
path = "{project_path!s}"
depth = 3
type = "folder"
date_format = "%m%d%Y"
separator = "period"
""")

    # Given: Mock configuration paths and initialize settings
    mocker.patch("neatfile.config.DEV_CONFIG_PATH", mock_dev)
    settings = SettingsManager.initialize()

    # When: Project settings are applied
    SettingsManager.apply_project_settings(project_name)

    # Then: Project settings override global settings
    assert isinstance(settings.project, Project)
    assert settings.project.name == project_name
    assert settings.project.path == project_path
    assert settings.project.depth == 3
    assert settings.project.project_type == "folder"
    assert settings.separator == Separator.PERIOD
    assert settings.date_format == "%m%d%Y"


def test_apply_project_settings_raises_on_missing_project(reset_settings_manager) -> None:
    """Verify applying non-existent project settings raises error."""
    # Given: Initialized settings
    SettingsManager.initialize()

    # When/Then: Applying non-existent project settings raises error
    with pytest.raises(cappa.Exit):
        SettingsManager.apply_project_settings("non_existent_project")


def test_apply_cli_settings_updates_settings(reset_settings_manager) -> None:
    """Verify CLI settings override existing settings."""
    # Given: Initialized settings
    settings = SettingsManager.initialize()
    cli_settings: dict[str, Any] = {
        "ignore_dotfiles": False,
        "date_format": "%m%d%Y",
        "separator": "dash",
        "none_value": None,  # Should be ignored
    }

    # When: Applying CLI settings
    SettingsManager.apply_cli_settings(cli_settings)

    # Then: Only non-None values are updated
    assert settings.date_format == "%m%d%Y"
    assert settings.ignore_dotfiles is False
    assert settings.separator == Separator.DASH
    assert "none_value" not in settings


def test_apply_cli_settings_raises_on_uninitialized(reset_settings_manager) -> None:
    """Verify applying CLI settings without initialization raises error."""
    # Given: Uninitialized settings
    assert SettingsManager._instance is None

    # When/Then: Applying CLI settings raises error
    with pytest.raises(cappa.Exit):
        SettingsManager.apply_cli_settings({"date_format": "%m%d%Y"})
