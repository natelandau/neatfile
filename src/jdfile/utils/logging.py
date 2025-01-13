"""Logging utilities for jdfile."""  # noqa: A005

import contextlib
import logging
import sys
from enum import Enum
from pathlib import Path

from loguru import logger
from rich.console import Console

console = Console()


class LogLevel(Enum):
    """Log levels."""

    INFO = 0
    DEBUG = 1
    TRACE = 2
    WARNING = 3
    ERROR = 4


def log_formatter(record: dict) -> str:
    """Use rich to style log messages.

    Args:
        record (dict): The record.

    Returns:
        str: The formatted message.
    """
    color_map = {
        "TRACE": "turquoise2",
        "DEBUG": "cyan",
        "DRYRUN": "bold blue",
        "INFO": "bold",
        "SUCCESS": "bold green",
        "WARNING": "bold yellow",
        "ERROR": "bold red",
        "CRITICAL": "bold white on red",
    }
    line_start_map = {
        "INFO": "",
        "DEBUG": "DEBUG | 🐞 ",
        "DRYRUN": "DRYRUN| 👉 ",
        "TRACE": "TRACE | 🔧 ",
        "WARNING": "⚠️ ",
        "SUCCESS": "✅ ",
        "ERROR": "❌ ",
        "CRITICAL": "💀 ",
        "EXCEPTION": "",
    }

    name = record["level"].name
    lvl_color = color_map.get(name, "bold")
    line_start = line_start_map.get(name, f"{name: <8} | ")

    msg = f"[{lvl_color}]{line_start}{{message}}[/{lvl_color}]"
    func_trace = f"[#c5c5c5]({record['name']}:{record['function']}:{record['line']})[/#c5c5c5]"

    return f"{msg} {func_trace}" if name in {"DEBUG", "TRACE"} else msg


def instantiate_logger(
    verbosity: int, log_file: Path, log_to_file: bool
) -> None:  # pragma: no cover
    """Instantiate the Loguru logger.

    Configure the logger with the specified verbosity level, log file path,
    and whether to log to a file.

    Args:
        verbosity (int): The verbosity level of the logger. Valid values are:
            - 0: Only log messages with severity level INFO and above will be displayed.
            - 1: Only log messages with severity level DEBUG and above will be displayed.
            - 2: Only log messages with severity level TRACE and above will be displayed.
            > 2: Include debug from installed libraries
        log_file (Path): The path to the log file where the log messages will be written.
        log_to_file (bool): Whether to log the messages to the file specified by `log_file`.
    """
    level = verbosity if verbosity < 3 else 2  # noqa: PLR2004

    logger.remove()
    with contextlib.suppress(TypeError, ValueError):
        logger.level("DRYRUN", no=21, color="<blue>", icon="👉")

    logger.add(
        console.print,
        level=LogLevel(level).name,
        colorize=True,
        format=log_formatter,  # type: ignore [arg-type]
    )
    if log_to_file:
        logger.add(
            log_file,
            level=LogLevel(level).name,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message} ({name}:{function}:{line})",
            rotation="50 MB",
            retention=2,
            compression="zip",
        )

    if verbosity > 2:  # noqa: PLR2004
        # Intercept standard package logs and redirect to Loguru
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


class InterceptHandler(logging.Handler):  # pragma: no cover
    """Intercepts standard logging and redirects to Loguru.

    This class is a logging handler that intercepts standard logging messages and redirects them to Loguru, a third-party logging library. When a logging message is emitted, this handler determines the corresponding Loguru level for the message and logs it using the Loguru logger.

    Methods:
        emit: Intercepts standard logging and redirects to Loguru.

    Examples:
    To use the InterceptHandler with the Python logging module:
    ```
    import logging
    from logging import StreamHandler

    from loguru import logger

    # Create a new InterceptHandler and add it to the Python logging module.
    intercept_handler = InterceptHandler()
    logging.basicConfig(handlers=[StreamHandler(), intercept_handler], level=logging.INFO)

    # Log a message using the Python logging module.
    logging.info("This message will be intercepted by the InterceptHandler and logged using Loguru.")
    ```
    """

    @staticmethod
    def emit(record) -> None:  # type: ignore [no-untyped-def]  # noqa: ANN001
        """Intercepts standard logging and redirects to Loguru.

        This method is called by the Python logging module when a logging message is emitted. It intercepts the message and redirects it to Loguru, a third-party logging library. The method determines the corresponding Loguru level for the message and logs it using the Loguru logger.

        Args:
            record: A logging.LogRecord object representing the logging message.
        """
        # Get corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = sys._getframe(6), 6  # noqa: SLF001
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())
