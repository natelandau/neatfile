"""Provide utilities for styled console output using rich formatting.

Implements a singleton pattern for consistent, styled message logging across an application. It supports multiple log levels with customizable styling including colors, emojis, and prefixes.

Changelog:
    - v2.2.1: Initial version
    - v2.3.1: Add support for dicts in messages
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import ParamSpec, TypeVar

from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class PrintStyle:
    """Style configuration for a log level."""

    name: str
    style: str = ""
    prefix: str = ""
    suffix: str = ""


DEFAULT_STYLES = [
    PrintStyle(name="TRACE", style="cadet_blue", prefix="🔍 "),
    PrintStyle(name="DEBUG", style="cadet_blue", prefix="🐛 "),
    PrintStyle(name="INFO", style="", prefix="", suffix=""),
    PrintStyle(name="SECONDARY", style="dim"),
    PrintStyle(name="NOTICE", style="bold"),
    PrintStyle(name="SUCCESS", style="", prefix="[bold green]✅ Success:[/bold green] "),
    PrintStyle(
        name="WARNING", style="", prefix="[dark_orange bold]🚧 Warning:[/dark_orange bold] "
    ),
    PrintStyle(name="ERROR", style="", prefix="[bold red]❌ Error:[/bold red] "),
    PrintStyle(
        name="CRITICAL",
        style="",
        prefix="[bold red reverse]💀 Critical:[/bold red reverse] ",
    ),
    PrintStyle(name="DRYRUN", style="", prefix="[blue bold]👉 Dry run:[/blue bold] "),
]


def merge_print_styles(
    default_styles: list[PrintStyle], user_styles: list[PrintStyle]
) -> list[PrintStyle]:
    """Merge default and user-defined print styles with user styles taking precedence.

    Customize specific log styles while preserving the default styles for other log levels. Normalize style names by converting to uppercase and replacing spaces/hyphens/dots with underscores.

    Args:
        default_styles (list[PrintStyle]): Base print styles to use as a foundation
        user_styles (list[PrintStyle]): Custom styles that override matching default styles

    Returns:
        list[PrintStyle]: Combined list of print styles with user overrides applied
    """
    # Create a dictionary from default_styles
    style_dict = {style.name.upper(): style for style in default_styles}

    # Transform user styles to conform to the default style names
    for user_style in user_styles:
        user_style.name = (
            user_style.name.upper().strip().replace(" ", "_").replace("-", "_").replace(".", "_")
        )

    # Update with user styles (overriding any duplicates)
    for user_style in user_styles:
        style_dict[user_style.name] = user_style

    return list(style_dict.values())


def get_style_by_name(styles: list[PrintStyle], name: str) -> PrintStyle | None:
    """Find a print style by its name using case-insensitive matching.

    Retrieve style configurations for specific log levels when applying formatting to messages.

    Args:
        styles (list[PrintStyle]): Collection of available print styles
        name (str): Name of the style to find (case-insensitive)

    Returns:
        PrintStyle | None: Matching style configuration if found, None otherwise
    """
    return next((style for style in styles if style.name.upper() == name.upper()), None)


class PrettyPrinter:
    """Manage consistent, styled message logging across an application.

    Singleton class to ensure uniform logging configuration throughout an application. It provides methods for outputting messages with different log levels and custom styling including colors, emojis, and prefixes.

    Use this class to:
    - Configure global debug and trace verbosity levels
    - Define custom styles for different message categories
    - Output consistently formatted log messages

    Attributes:
        is_debug (bool): Toggle debug message visibility
        is_trace (bool): Toggle trace message visibility
        styles (list[PrintStyle]): Style configurations for different message types
    """

    _instance = None
    _initialized = False

    def __new__(cls) -> "PrettyPrinter":
        """Create a new PrettyPrinter instance if it doesn't exist."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the PrettyPrinter instance."""
        if not PrettyPrinter._initialized:
            self.is_debug = False
            self.is_trace = False
            self.styles = DEFAULT_STYLES
            PrettyPrinter._initialized = True

    def configure(
        self,
        styles: list[PrintStyle] = [],
        *,
        debug: bool = False,
        trace: bool = False,
    ) -> None:
        """Set up logging verbosity and custom styles for the printer.

        Configure the global logging behavior by enabling/disabling debug and trace messages and customizing message styles.

        Args:
            styles (list[PrintStyle], optional): Custom styles to override defaults
            debug (bool, optional): Enable debug level messages. Defaults to False
            trace (bool, optional): Enable trace level messages
                Defaults to False
        """
        self.is_debug = debug
        self.is_trace = trace

        self.styles = merge_print_styles(DEFAULT_STYLES, styles)

    def _print(self, style: PrintStyle, message: str | Text | dict, **kwargs: P.kwargs) -> None:  # type: ignore [valid-type]
        """Output a styled message according to the specified log level.

        Internal method that handles message filtering, prefix addition, and style application based on the configured log level.

        Args:
            style (PrintStyle): Style configuration to apply to the message
            message (str | Text | dict): Content to output
            **kwargs (P.kwargs): Additional arguments passed to console.print()
        """
        if style.name in {"TRACE", "DEBUG"} and not (
            self.is_trace if style.name == "TRACE" else self.is_debug
        ):
            return

        prefix = style.prefix
        suffix = style.suffix
        style_open = f"[{style.style}]" if style.style and not style.style.isspace() else ""
        style_close = f"[/{style.style}]" if style.style and not style.style.isspace() else ""

        if isinstance(message, str):
            message = re.sub(r"`([^`]+)`", r"[bold cyan on black]\1[/bold cyan on black]", message)

        if isinstance(message, dict):
            message = json.dumps(message, indent=2)

        console.print(f"{style_open}{prefix}{message}{suffix}{style_close}", **kwargs)

    @staticmethod
    def rule(message: str = "", **kwargs: P.kwargs) -> None:  # type: ignore [valid-type]
        """Print a horizontal rule with optional message.

        Create visual separation in console output with an optional centered message.

        Args:
            message (str, optional): Text to display in the rule. Defaults to empty
            **kwargs (P.kwargs): Additional styling options for console.rule()
        """
        console.rule(message, **kwargs)

    def all_styles(self) -> None:
        """Show all available styles."""
        grid = Table.grid(padding=(0, 3))

        for style in self.styles:
            prefix = style.prefix
            suffix = style.suffix
            style_open = f"[{style.style}]" if style.style and not style.style.isspace() else ""
            style_close = f"[/{style.style}]" if style.style and not style.style.isspace() else ""

            grid.add_row(
                style.name.lower(),
                f"{style_open}{prefix}The quick brown fox jumps over the lazy dog{suffix}{style_close}",
            )

        self.rule("Available styles")
        console.print(grid)
        self.rule()

    def __getattr__(self, name: str) -> Callable[[str | Text | dict], None]:
        """Create logging methods dynamically based on style names.

        Enable method-style logging (e.g., pp.info("message")) by automatically generating logging functions for each defined style.

        Args:
            name (str): Style name to create a logging method for

        Returns:
            Callable[[str | Text | dict], None]: Function that logs messages with the specified style

        Raises:
            AttributeError: If no style exists matching the requested name
        """
        style = get_style_by_name(self.styles, name)
        if style is None:
            msg = f"'Printer' object has no attribute '{name}'"
            raise AttributeError(msg)

        return lambda message, **kwargs: self._print(style, message, **kwargs)


pp = PrettyPrinter()
