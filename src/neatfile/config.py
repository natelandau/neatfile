"""Instantiate settings default values."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cappa
from dynaconf import Dynaconf, ValidationError, Validator

from neatfile.constants import (
    DEFAULT_CONFIG_PATH,
    DEV_CONFIG_PATH,
    USER_CONFIG_PATH,
    DateRegion,
    InsertLocation,
    Separator,
    TransformCase,
)
from neatfile.utils import console, pp


@dataclass
class SettingsManager:
    """Manage application settings through a singleton pattern.

    Provide centralized configuration management with support for default values, project-specific overrides, and CLI argument integration. Handles initialization of settings from config files, environment variables, and runtime overrides while maintaining type safety through validators.
    """

    _instance: Dynaconf | None = None

    @classmethod
    def initialize(cls) -> Dynaconf:
        """Create and configure a new Dynaconf settings instance with default values.

        Configure settings with environment variables, config files, and validators for all supported settings. Return existing instance if already initialized.

        Returns:
            Dynaconf: The configured settings instance with all validators registered.
        """
        if cls._instance is not None:
            return cls._instance

        settings = Dynaconf(
            environments=False,
            envvar_prefix="NEATFILE",
            settings_files=[DEFAULT_CONFIG_PATH, USER_CONFIG_PATH, DEV_CONFIG_PATH],
            validate_on_update=True,
        )

        # Register all validators at once
        settings.validators.register(
            Validator("date_format", default="%Y-%m-%d", cast=str),
            Validator("date_region", default="US", cast=lambda v: DateRegion[v.upper()]),
            Validator("ignore_dotfiles", cast=bool, default=True),
            Validator("ignore_file_regex", default="^$", cast=lambda v: str(v) or "^$"),
            Validator("ignored_files", default=[], cast=list),
            Validator(
                "insert_location",
                default="before",
                cast=lambda v: InsertLocation[v.upper()],
            ),
            Validator("match_case_list", default=[], cast=list),
            Validator("overwrite_existing", cast=bool, default=False),
            Validator(
                "separator",
                default="ignore",
                cast=lambda v: Separator[v.upper()] if isinstance(v, str) else v,
            ),
            Validator("split_words", cast=bool, default=False),
            Validator("stopwords", default=[], cast=list),
            Validator("strip_stopwords", cast=bool, default=True),
            Validator(
                "transform_case",
                default="ignore",
                cast=lambda v: TransformCase[v.upper()],
            ),
        )

        try:
            settings.validators.validate_all()
        except ValidationError as e:
            accumulative_errors = e.details
            pp.error(accumulative_errors)
            raise cappa.Exit(code=1) from e
        except ValueError as e:
            console.print(e)
            raise cappa.Exit(code=1) from e

        cls._instance = settings
        return settings

    @classmethod
    def apply_project_settings(cls, project_name: str) -> None:
        """Override global settings with project-specific configuration values.

        Load settings for the specified project from the configuration file and update the global settings singleton. Create a standardized Project object and apply any project-specific overrides for settings like date formatting, file handling, and text transformations.

        Args:
            project_name (str): Name of the project whose settings should be applied.

        Raises:
            cappa.Exit: If settings are not initialized or project name is not found in config.
        """
        # Avoid circular import
        from neatfile.models import Project  # noqa: PLC0415

        settings = cls._instance
        if settings is None:  # pragma: no cover
            msg = "Settings not initialized"
            pp.error(msg)
            raise cappa.Exit(code=1)

        if not settings.get("projects", {}) or project_name not in settings.projects:
            msg = f"Project `{project_name}` not found in the configuration file."
            pp.error(msg)
            raise cappa.Exit(code=1)

        project_config = settings.projects[project_name]

        # Create standardized project object
        project = Project(
            name=project_name,
            path=Path(project_config.path),
            depth=project_config.get("depth", 2),
            project_type=project_config.get("type", "folder"),
        )

        # Build override dict with project-specific settings
        overrides = {
            "project": project,
            **{
                key: project_config.get(key, settings.get(key))
                for key in [
                    "date_format",
                    "ignore_dotfiles",
                    "ignore_file_regex",
                    "ignored_files",
                    "insert_location",
                    "match_case_list",
                    "overwrite_existing",
                    "separator",
                    "split_words",
                    "stopwords",
                    "strip_stopwords",
                    "transform_case",
                    "user_terms",
                ]
            },
        }
        settings.update(overrides)

    @classmethod
    def apply_cli_settings(cls, cli_settings: dict[str, Any]) -> None:
        """Override existing settings with non-None values from CLI arguments.

        Update the settings singleton with any non-None values provided via command line arguments, preserving existing values for unspecified settings.

        Args:
            cli_settings (dict[str, Any]): Dictionary of settings from CLI arguments to apply as overrides.

        Raises:
            cappa.Exit: If settings singleton has not been initialized.
        """
        settings = cls._instance
        if settings is None:  # pragma: no cover
            msg = "Settings not initialized"
            pp.error(msg)
            raise cappa.Exit(code=1)

        # Filter out None values to avoid overriding with None
        cli_overrides = {k: v for k, v in cli_settings.items() if v is not None}
        settings.update(cli_overrides)


# Initialize settings singleton
settings = SettingsManager.initialize()
