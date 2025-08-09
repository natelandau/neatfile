"""The neatfile cli."""

from __future__ import annotations

import shutil
from pathlib import Path  # noqa: TC003
from typing import Annotated

import cappa
from nclutils import console, pp, print_debug
from rich.markdown import Markdown
from rich.traceback import install

from neatfile import settings
from neatfile.commands import execute_command
from neatfile.config import SettingsManager
from neatfile.constants import (
    DEFAULT_CONFIG_PATH,
    USER_CONFIG_PATH,
    VERSION,
    PrintLevel,
    Separator,
    TransformCase,
)


def config_subcommand(neatfile: NeatFile) -> None:
    """Configure settings based on the provided command and arguments.

    Update the global settings object with values from the command line arguments and configuration file. Handle project-specific settings if a project is specified.

    Args:
        neatfile (NeatFile): The main CLI application object containing command and configuration options.

    Raises:
        cappa.Exit: If the command is not found.
    """
    pp.configure(
        debug=neatfile.verbosity in {PrintLevel.DEBUG, PrintLevel.TRACE},
        trace=neatfile.verbosity == PrintLevel.TRACE,
    )

    # Apply command-specific settings
    cli_settings = {
        "subcommand": neatfile.command.__class__.__name__.lower(),
        "confirm_changes": getattr(neatfile.command, "confirm_changes", False),
        "date": getattr(neatfile.command, "date", None),
        "date_format": getattr(neatfile.command, "date_format", None),
        "date_only": getattr(neatfile.command, "date_only", False),
        "dryrun": getattr(neatfile, "dryrun", False),
        "files": getattr(neatfile.command, "files", []),
        "force": getattr(neatfile.command, "force", False),
        "full_tree": getattr(neatfile.command, "full_tree", False),
        "overwrite": getattr(neatfile.command, "overwrite", False),
        "separator": getattr(neatfile.command, "separator", None),
        "transform_case": getattr(neatfile.command, "transform_case", None),
        "user_terms": getattr(neatfile.command, "user_terms", ()),
        "file_search_depth": getattr(neatfile.command, "file_search_depth", None),
    }

    SettingsManager.apply_cli_settings(cli_settings)

    # Configure project if specified
    if project_name := getattr(neatfile, "project_name", ""):
        try:
            SettingsManager.apply_project_settings(project_name)
        except ValueError as e:
            pp.error(str(e))
            raise cappa.Exit(code=1) from e

    if pp.is_trace:
        print_debug(
            custom=[
                {"Settings": settings.to_dict()},
                {"neatfile": neatfile.__dict__},
                {"Neatfile Version": VERSION},
            ],
            envar_prefix="neatfile",
            packages=["questionary", "cappa", "dynaconf", "rich", "spacy"],
        )


@cappa.command(
    name="neatfile",
    description="""

**Filename cleaning and normalization**

-   Remove special characters
-   Trim multiple separators (`word----word` becomes `word-word`)
-   Normalize to `lowercase`, `uppercase`, `Sentence case`, or `Title Case`
-   Normalize all files to a common word separator (`_`, `-`, ` `, `.`)
-   Enforce lowercase file extensions
-   Remove common English stopwords
-   Split `camelCase` words into separate words (`camel Case`)

**Date parsing**

-   Parse dates in filenames in many different formats
-   Fall back to file creation date if no date is found in the filename
-   Normalize dates in filenames to a preferred format
-   Add the date to the beginning or the end of the filename or remove it entirely

**File organization**

-   Set up projects with directory trees in the config file
-   Match terms in filenames to folder names and move files into the appropriate folders
-   Use vector matching to find similar terms
-   Respect the [Johnny Decimal](https://johnnydecimal.com) system if you use it
-   Optionally, add `.neatfile` files to directories containing a list of words that will match files

**Configuration**

To set your preferences and create projects, you'll need to create a configuration file. Neatfile will look for a file at `~/.config/neatfile/config.toml` or your `$XDG_CONFIG_HOME/neatfile/config.toml` if set.
    """,
)
class NeatFile:
    """A CLI tool that automatically normalizes and organizes your files based on customizable rules."""

    command: cappa.Subcommands[
        CleanCommand | ConfigCommand | SortCommand | ProcessCommand | TreeCommand
    ]

    project_name: Annotated[
        str,
        cappa.Arg(
            long="project",
            short="p",
            help="Specify a project from the configuration file.",
            propagate=True,
        ),
    ] = ""
    verbosity: Annotated[
        PrintLevel,
        cappa.Arg(
            short=True,
            count=True,
            help="Verbosity level (`-v` or `-vv`)",
            choices=[],
            show_default=False,
            propagate=True,
        ),
    ] = PrintLevel.INFO
    dryrun: Annotated[
        bool,
        cappa.Arg(
            long="dry-run",
            short="-n",
            help="Preview changes without modifying files",
            show_default=False,
            propagate=True,
        ),
    ] = False


@cappa.command(
    name="clean",
    description="""\
Perform the following transformations on a filename:

-   Remove special characters
-   Trim multiple separators (`word----word` becomes `word-word`)
-   Normalize to `lowercase`, `uppercase`, `Sentence case`, or `Title Case`
-   Normalize all word separators to a common one (`_`, `-`, ` `, `.`)
-   Enforce lowercase file extensions
-   Remove common English stopwords
-   Split `camelCase` words into separate words (`camel Case`)
-   Add a date to the filename in your preferred format (removing dates already present in the filename)

Learn more [in the README](https://github.com/natelandau/neatfile).
""",
)
class CleanCommand:
    """Clean and normalize filenames."""

    files: Annotated[
        list[Path],
        cappa.Arg(
            help="The files to clean. If a directory is provided, all files in the directory will be cleaned, not the directory itself.",
            required=True,
        ),
    ]

    confirm_changes: Annotated[
        bool,
        cappa.Arg(
            long="confirm",
            short="c",
            help="Confirm changes before applying them",
            show_default=False,
        ),
    ] = False
    date: Annotated[
        str | None,
        cappa.Arg(
            long="date",
            short="d",
            help="Specify a date to use for the filename (ignores dates found in filename)",
            show_default=False,
        ),
    ] = None

    date_format: Annotated[
        str | None,
        cappa.Arg(
            long="date-format",
            short="f",
            help="Specify a date format to use for the filename (e.g. `%Y-%m-%d`)",
            show_default=False,
        ),
    ] = None
    date_only: Annotated[
        bool,
        cappa.Arg(
            help="Add a date to the filename but make no other changes",
            show_default=False,
        ),
    ] = False
    file_search_depth: Annotated[
        int | None,
        cappa.Arg(
            long="depth",
            help="Depth to search for files if using a wildcard",
            show_default=False,
        ),
    ] = None
    force: Annotated[
        bool,
        cappa.Arg(
            help="Do not prompt for confirmation before making changes",
            show_default=False,
        ),
    ] = False
    overwrite: Annotated[
        bool,
        cappa.Arg(
            help="Overwrite existing files rather than creating a backup",
            show_default=False,
        ),
    ] = False
    transform_case: Annotated[
        str | None,
        cappa.Arg(
            choices=[c.name for c in TransformCase],
            long="case",
            help="Transform the case of the filename",
            show_default=True,
            parse=lambda x: x.upper(),
        ),
    ] = None
    separator: Annotated[
        str | None,
        cappa.Arg(
            choices=[c.name for c in Separator],
            long=["separator", "sep"],
            help="Separator to use for the filename.",
            show_default=False,
            parse=lambda x: x.upper(),
        ),
    ] = None

    def __call__(self) -> None:
        """Call the command."""
        if settings.date_only and not settings.date_format:
            pp.error("`date_format` is not specified")
            raise cappa.Exit(code=1)

        execute_command()


@cappa.command(name="config")
class ConfigCommand:
    """View and create a user configuration file."""

    create: Annotated[
        bool,
        cappa.Arg(help="Create a user configuration file", show_default=False),
    ] = False

    def __call__(self) -> None:
        """Call the command."""
        if self.create:
            if USER_CONFIG_PATH.exists():
                pp.info(f"User configuration file already exists: {USER_CONFIG_PATH}")
                raise cappa.Exit(code=1)

            if settings.dryrun:
                pp.dryrun(f"Would create configuration file: {USER_CONFIG_PATH}")
                raise cappa.Exit(code=0)

            USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(DEFAULT_CONFIG_PATH, USER_CONFIG_PATH)
            pp.success(f"User config file created: {USER_CONFIG_PATH}")
            raise cappa.Exit(code=0)

        current_config = USER_CONFIG_PATH if USER_CONFIG_PATH.exists() else DEFAULT_CONFIG_PATH

        pp.rule("Current Configuration")
        console.print(Markdown("```toml\n" + current_config.read_text() + "\n```"))

        if not USER_CONFIG_PATH.exists():
            pp.info("Using default configuration.")
            pp.secondary(f"No user configuration file found: {USER_CONFIG_PATH}")
            pp.secondary("To create a user configuration file, run `neatfile config --create`")
        else:
            pp.info(f"User configuration file found: {USER_CONFIG_PATH}")


@cappa.command(
    name="process",
    description="""\
Perform the following transformations on a filename:

-   Remove special characters
-   Trim multiple separators (`word----word` becomes `word-word`)
-   Normalize to `lowercase`, `uppercase`, `Sentence case`, or `Title Case`
-   Normalize all word separators to a common one (`_`, `-`, ` `, `.`)
-   Enforce lowercase file extensions
-   Remove common English stopwords
-   Split `camelCase` words into separate words (`camel Case`)
-   Add a date to the filename in your preferred format (removing dates already present in the filename)

Sort files into a project directory:

-   Specify the project with the `--project` flag
-   Match terms in filenames to directory names and move files into the appropriate directory
-   Use vector matching to find similar terms

**Note:** Projects must be defined in the configuration file.

Learn more [in the README](https://github.com/natelandau/neatfile).
""",
)
class ProcessCommand:
    """Clean and sort files."""

    files: Annotated[
        list[Path],
        cappa.Arg(
            help="The files to clean. If a directory is provided, all files in the directory will be cleaned, not the directory itself.",
            required=True,
        ),
    ]

    confirm_changes: Annotated[
        bool,
        cappa.Arg(
            long="confirm",
            short="c",
            help="Confirm changes before applying them",
            show_default=False,
        ),
    ] = False
    date: Annotated[
        str | None,
        cappa.Arg(
            long="date",
            short="d",
            help="Specify a date to use for the filename (ignores dates found in filename)",
            show_default=False,
        ),
    ] = None
    file_search_depth: Annotated[
        int | None,
        cappa.Arg(
            long="depth",
            help="Depth to search for files if using a wildcard",
            show_default=False,
        ),
    ] = None
    user_terms: Annotated[
        tuple[str, ...],
        cappa.Arg(
            long="term",
            short="t",
            help="Term used to match files to folders. Add multiple terms with additional `--term` flags",
            show_default=False,
        ),
    ] = ()

    date_format: Annotated[
        str | None,
        cappa.Arg(
            long="date-format",
            short="f",
            help="Specify a date format to use for the filename (e.g. `%Y-%m-%d`)",
            show_default=False,
        ),
    ] = None
    date_only: Annotated[
        bool,
        cappa.Arg(
            help="Add a date to the filename but make no other changes",
            show_default=False,
        ),
    ] = False
    force: Annotated[
        bool,
        cappa.Arg(
            help="Do not prompt for confirmation before making changes",
            show_default=False,
        ),
    ] = False
    overwrite: Annotated[
        bool,
        cappa.Arg(
            help="Overwrite existing files rather than creating a backup",
            show_default=False,
        ),
    ] = False
    transform_case: Annotated[
        str | None,
        cappa.Arg(
            choices=[c.name for c in TransformCase],
            long="case",
            help="Transform the case of the filename",
            show_default=True,
            parse=lambda x: x.upper(),
        ),
    ] = None
    separator: Annotated[
        str | None,
        cappa.Arg(
            choices=[c.name for c in Separator],
            long=["separator", "sep"],
            help="Separator to use for the filename.",
            show_default=False,
            parse=lambda x: x.upper(),
        ),
    ] = None

    def __call__(self) -> None:
        """Call the command."""
        if settings.date_only and not settings.date_format:
            pp.error("`date_format` is not specified")
            raise cappa.Exit(code=1)

        if not settings.get("project", {}):
            pp.error("`project` is not specified")
            raise cappa.Exit(code=1)

        execute_command()


@cappa.command(
    name="sort",
    description="""\
Projects must be defined in the configuration file.

-   Specify the project with the `--project` flag
-   Match terms in filenames to directory names and move files into the appropriate directory
-   Use vector matching to find similar terms

Learn more [in the README](https://github.com/natelandau/neatfile/).
""",
)
class SortCommand:
    """Sort files into a project folder."""

    files: Annotated[
        list[Path],
        cappa.Arg(
            help="The files to clean. If a directory is provided, all files in the directory will be cleaned, not the directory itself.",
            required=True,
        ),
    ]

    confirm_changes: Annotated[
        bool,
        cappa.Arg(
            long="confirm",
            short="c",
            help="Confirm changes before applying them",
            show_default=False,
        ),
    ] = False
    file_search_depth: Annotated[
        int | None,
        cappa.Arg(
            long="depth",
            help="Depth to search for files if using a wildcard",
            show_default=False,
        ),
    ] = None
    force: Annotated[
        bool,
        cappa.Arg(
            help="Do not prompt for confirmation before making changes",
            show_default=False,
        ),
    ] = False
    overwrite: Annotated[
        bool,
        cappa.Arg(
            help="Overwrite existing files rather than creating a backup",
            show_default=False,
        ),
    ] = False

    user_terms: Annotated[
        tuple[str, ...],
        cappa.Arg(
            long="term",
            short="t",
            help="Term used to match files to folders. Add multiple terms with additional `--term` flags",
            show_default=False,
        ),
    ] = ()

    def __call__(self) -> None:
        """Call the command."""
        if not settings.get("project", {}):
            pp.error("`project` is not specified")
            raise cappa.Exit(code=1)

        execute_command()


@cappa.command(name="tree")
class TreeCommand:
    """Print a tree representation of the project folder."""

    def __call__(self) -> None:
        """Call the command."""
        if settings.get("project"):
            console.print(settings.project.tree())
        else:
            pp.error("You must specify a project name with the `--project` flag.")
            raise cappa.Exit(code=1)


def main() -> None:  # pragma: no cover
    """Initialize and execute the command line interface.

    Parse command line arguments, configure settings, and execute the appropriate command. Handle keyboard interrupts gracefully by exiting with a status code of 1.

    Raises:
        cappa.Exit: If a keyboard interrupt occurs.
    """
    install(show_locals=False)

    try:
        cappa.invoke(obj=NeatFile, deps=[config_subcommand], completion=False)
    except KeyboardInterrupt as e:
        pp.info("Exiting...")
        raise cappa.Exit(code=1) from e


if __name__ == "__main__":  # pragma: no cover
    main()
