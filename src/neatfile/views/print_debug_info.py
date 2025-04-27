"""Print debug information in a pretty way."""

import os
import platform
import sys
from dataclasses import dataclass
from importlib import metadata
from importlib.metadata import packages_distributions

from rich.table import Table

from neatfile.utils import console, pp


@dataclass
class Variable:
    """Dataclass describing an environment variable."""

    name: str
    value: str


@dataclass
class Package:
    """Dataclass describing a Python package."""

    name: str
    version: str

    def __eq__(self, other: object) -> bool:
        """Check if two packages are equal.

        Args:
            other (object): The other package to compare to.

        Returns:
            bool: True if the packages are equal, False otherwise.
        """
        if not isinstance(other, Package):  # pragma: no cover
            return False

        return self.name == other.name

    def __hash__(self) -> int:
        """Hash the package.

        Returns:
            int: The hash of the package.
        """
        return hash(self.name)


@dataclass
class Environment:
    """Dataclass to store environment information."""

    interpreter_name: str
    interpreter_version: str
    interpreter_path: str
    platform: str
    packages: list[Package]
    variables: list[Variable]


def _interpreter_name_version() -> tuple[str, str]:
    if hasattr(sys, "implementation"):
        impl = sys.implementation.version
        version = f"{impl.major}.{impl.minor}.{impl.micro}"
        kind = impl.releaselevel
        if kind != "final":  # pragma: no cover
            version += kind[0] + str(impl.serial)

        return sys.implementation.name, version

    return "", "0.0.0"  # pragma: no cover


def _get_version(dist: str) -> str:
    """Get the version number of an installed Python package.

    Safely retrieve the version string for an installed package, falling back to '0.0.0' if not found. Use this function to get version information for dependency tracking and compatibility checks.

    Args:
        dist (str): Name of the Python package/distribution to check

    Returns:
        str: Version string of the package if installed, otherwise '0.0.0'
    """
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:  # pragma: no cover
        return "0.0.0"


def _get_packages(
    package_names: list[str] | None = None, *, all_packages: bool = False
) -> set[Package]:
    """Retrieve installed Python packages based on filtering criteria.

    Get either all installed packages or a filtered subset based on package names. Use this to get package version information for debugging and dependency tracking.

    Args:
        package_names (list[str] | None): List of package names to filter by. If None and all_packages is False, returns empty set. Defaults to None.
        all_packages (bool): Whether to return all installed packages regardless of package_names. Defaults to False.

    Returns:
        set[Package]: Set of Package objects containing name and version information for matching packages.
    """
    if all_packages:
        return {
            Package(value[0], _get_version(value[0]))
            for key, value in packages_distributions().items()
        }

    return (
        {
            Package(value[0], _get_version(value[0]))
            for key, value in packages_distributions().items()
            if key in package_names
        }
        if package_names
        else set()
    )


def _get_envars(envar_prefix: str | None = None) -> list[Variable]:
    """Get environment variables filtered by an optional prefix.

    Retrieve environment variables, always including PYTHONPATH and optionally filtering others by a prefix. Use this to get relevant environment variables for debugging and configuration purposes.

    Args:
        envar_prefix (str | None, optional): Prefix to filter environment variables. Only variables starting with this prefix will be included. Defaults to None.

    Returns:
        list[Variable]: List of Variable objects containing name and value pairs for matching environment variables.
    """
    if envar_prefix is None or not envar_prefix:
        variables = ["PYTHONPATH"]
    else:
        variables = ["PYTHONPATH", *[var for var in os.environ if var.startswith(envar_prefix)]]

    return [Variable(var, val) for var in variables if (val := os.getenv(var))]


def print_debug(  # noqa: C901
    envar_prefix: str | None = None,
    custom: list[dict[str, dict[str, str]] | dict[str, str]] | None = None,
    packages: list[str] | None = None,
    *,
    all_packages: bool = False,
) -> None:
    """Display formatted debug information for troubleshooting and bug reports.

    Generate comprehensive debug output including system details, Python interpreter info, environment variables, installed package versions and custom debug data in a structured, readable format.

    Args:
        envar_prefix (str | None): Prefix to filter environment variables. Only variables starting with this prefix will be included. Defaults to None.
        custom (list[dict[str, dict[str, str] | str]] | None): Additional debug data to display. Each dict represents a section with key-value pairs. Defaults to None.
        packages (list[str] | None): List of package names to check versions for. Defaults to None.
        all_packages (bool): Show all installed package names and versions. Defaults to False.

    Changelog:
        - v2.2.1: Initial version
        - v2.3.4: Accept strings in custom dicts
    """
    if custom is None:
        custom = []

    py_name, py_version = _interpreter_name_version()
    pkgs = _get_packages(packages, all_packages=all_packages)
    env_info = Environment(
        interpreter_name=py_name,
        interpreter_version=py_version,
        interpreter_path=sys.executable,
        platform=platform.platform(),
        variables=_get_envars(envar_prefix),
        packages=sorted(pkgs, key=lambda x: x.name) if pkgs else [],
    )

    pp.rule("debug info")

    var_grid = Table.grid(padding=(0, 5))
    var_grid.add_column(style="bold")
    var_grid.add_column(style="cyan")
    env_grid = Table.grid(padding=(0, 5), pad_edge=True)
    env_grid.add_column(style="dim")
    env_grid.add_column(style="cyan dim")
    pkg_grid = Table.grid(padding=(0, 5), pad_edge=True)
    pkg_grid.add_column(style="dim")
    pkg_grid.add_column(style="cyan dim")

    var_grid.add_row("System:", f"{env_info.platform}")
    var_grid.add_row(
        "Python:",
        f"{env_info.interpreter_name} {env_info.interpreter_version} [dim]({env_info.interpreter_path})[/dim]",
    )
    for var in env_info.variables:
        env_grid.add_row(var.name, var.value)

    if env_info.packages:
        for pkg in env_info.packages:
            pkg_grid.add_row(pkg.name, pkg.version)

    for custom_dict in custom:
        custom_grid = Table.grid(padding=(0, 5), pad_edge=True)
        custom_grid.add_column(style="dim")
        custom_grid.add_column(style="cyan dim")
        for key, value in custom_dict.items():
            if isinstance(value, str):
                var_grid.add_row(f"{key}:", value)
            else:
                pp.notice(f"{key}:")
                for k, v in value.items():
                    custom_grid.add_row(str(k), str(v))
                console.print(custom_grid)

    console.print(var_grid)
    if env_info.variables:
        pp.notice("Environment variables:")
        console.print(env_grid)
    if env_info.packages:
        pp.notice("Installed packages:")
        console.print(pkg_grid)

    pp.rule()
