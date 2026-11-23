"""Duty tasks for the project."""

from __future__ import annotations

import os
import random
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from duty import duty, tools

if TYPE_CHECKING:
    from duty.context import Context

PY_SRC_PATHS = (Path(_) for _ in ("src/", "tests/", "duties.py", "scripts/") if Path(_).exists())
PY_SRC_LIST = tuple(str(_) for _ in PY_SRC_PATHS)
CI = os.environ.get("CI", "").lower() in {"1", "true", "yes"}

# Every tracked file the test suite reads; a change anywhere else leaves a passing test gate cached
TEST_GATE_PATHS = ("src/", "tests/", "duties.py", "pyproject.toml", "uv.lock")
TEST_REPORT_PATH = ".cache/pytest.xml"


NOUNS = [
    "fish",
    "shark",
    "people",
    "chicken",
    "cow",
    "pig",
    "harpsichord",
    "woman",
    "life",
    "ostrich",
    "world",
    "school",
    "state",
    "family",
    "student",
    "lion",
    "country",
    "piano",
    "guitar",
    "fox",
    "tuba",
    "clarinet",
    "bassoon",
    "company",
    "banjo",
    "bass",
    "oboe",
    "cello",
    "government",
    "whale",
    "night",
    "eagle",
    "duck",
    "water",
    "room",
    "mother",
    "area",
    "money",
    "story",
    "fact",
    "puppy",
    "lot",
    "cockroach",
    "study",
    "book",
    "rat",
    "viola",
    "word",
    "business",
    "parrot",
    "hippo",
    "violin",
    "eel",
    "tuna",
    "hyena",
    "dolphin",
    "father",
    "power",
    "trout",
    "armadillo",
    "mouse",
    "mongoose",
    "spider",
    "car",
    "city",
    "horse",
    "team",
    "snake",
    "body",
    "back",
    "parent",
    "nurse",
    "pirahna",
    "office",
    "health",
    "person",
    "art",
    "war",
    "history",
    "crow",
    "result",
    "koala",
    "morning",
    "hawk",
    "research",
    "girl",
    "elephant",
    "moment",
    "teacher",
    "albatross",
    "education",
]


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string.

    Args:
        text (str): String to remove ANSI escape sequences from.

    Returns:
        str: String without ANSI escape sequences.
    """
    ansi_chars = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]")

    # Replace [ with \[ so rich doesn't interpret output as style tags
    return ansi_chars.sub("", text).replace("[", r"\[")


def pyprefix(title: str) -> str:
    """Add a prefix to the title if CI is true.

    Returns:
        str: Title with prefix if CI is true.
    """
    if CI:
        prefix = f"(python{sys.version_info.major}.{sys.version_info.minor})"
        return f"{prefix:14}{title}"
    return title


def gated(
    name: str, command: list[str], paths: tuple[str, ...] = (), junit_path: str | None = None
) -> list[str]:
    """Wrap a check in gate-cache so it skips when it already passed on the same file content.

    Args:
        name (str): Stable gate name. Put any input git does not track after an `@`.
        command (list[str]): The check command to run.
        paths (tuple[str, ...]): Git pathspecs the check reads. Empty means the whole repository.
        junit_path (str | None): JUnit report the command writes, recorded per test in gate-cache stats.

    Returns:
        list[str]: The gate-cache command line.
    """
    path_args: list[str] = [arg for path in paths for arg in ("--path", path)]
    junit_args: list[str] = ["--junit", junit_path] if junit_path else []
    return ["gate-cache", "--name", name, *path_args, *junit_args, "--", *command]


@duty(silent=True, post=["dev_clean"])
def clean(ctx: Context) -> None:
    """Clean the project."""
    ctx.run("rm -rf .cache")
    ctx.run("rm -rf build")
    ctx.run("rm -rf dist")
    ctx.run("rm -rf pip-wheel-metadata")
    ctx.run("find . -type d -name __pycache__ | xargs rm -rf")
    ctx.run("find . -name '.DS_Store' -delete")


@duty
def ruff(ctx: Context) -> None:
    """Check the code quality with ruff."""
    ctx.run(
        tools.ruff.check(*PY_SRC_LIST, fix=False, config="pyproject.toml"),
        title=pyprefix("code quality check"),
        command="ruff check --config pyproject.toml --no-fix src/",
    )


@duty
def format(ctx: Context) -> None:  # noqa: A001
    """Format the code with ruff."""
    ctx.run(
        tools.ruff.format(*PY_SRC_LIST, check=True, config="pyproject.toml"),
        title=pyprefix("code formatting"),
        command="ruff format --check --config pyproject.toml src/",
    )


@duty
def ty(ctx: Context) -> None:
    """Type check the code with ty."""
    # Uncaptured so CI's TY_OUTPUT_FORMAT=github annotations start their lines, which GitHub requires
    ctx.run(["ty", "check"], title=pyprefix("ty check"), command="ty check", capture=False)


@duty
def typos(ctx: Context) -> None:
    """Check the code with typos."""
    ctx.run(
        gated(name="typos", command=["typos", "--config", ".typos.toml"]),
        title=pyprefix("typos check"),
        command="typos --config .typos.toml",
    )


@duty
def prek(ctx: Context) -> None:
    """Run prek hooks."""
    # Other duties already run these hooks
    skipped_hooks = "pytest,ruff-check,ruff-format,ty,typos"
    prek_command: list[str] = ["prek", "run", "--all-files", "--show-diff-on-failure"]
    ctx.run(
        gated(name="prek", command=["env", f"SKIP={skipped_hooks}", *prek_command]),
        title=pyprefix("prek hooks"),
    )


@duty(pre=[ruff, format, ty, typos, prek], capture=CI)
def lint(ctx: Context) -> None:
    """Run all linting duties."""


@duty(capture=CI)
def update(ctx: Context) -> None:
    """Update the project."""
    ctx.run(["uv", "lock", "--upgrade"], title="update uv lock")
    ctx.run(["uv", "sync"], title="update uv dependencies")
    ctx.run(["prek", "autoupdate"], title="prek autoupdate")


@duty
def test(ctx: Context, *cli_args: str) -> None:
    """Test package and generate coverage reports."""
    pytest_command: list[str] = [
        "pytest",
        "tests",
        "src",
        "--color=yes",
        "--config-file=pyproject.toml",
        "--cov",
        "--cov-config=pyproject.toml",
        "--cov-report=xml",
        "--cov-report=term",
        f"--junitxml={TEST_REPORT_PATH}",
        # Overrides the configured --exitfirst so CI reports every failure, not just the first
        *(["--maxfail=0"] if CI else []),
        *cli_args,
    ]
    # A filtered run such as `duty test -k foo` must not mark the full suite as passed
    command: list[str] = (
        pytest_command
        if cli_args
        else gated(
            name=f"test@py{sys.version_info.major}.{sys.version_info.minor}",
            command=pytest_command,
            paths=TEST_GATE_PATHS,
            junit_path=TEST_REPORT_PATH,
        )
    )
    ctx.run(command, title=pyprefix("Running tests"), capture=CI)


@duty()
def dev_clean(ctx: Context) -> None:
    """Clean the development environment."""
    # We import these here to avoid importing code before pytest-cov is initialized
    from neatfile.constants import DEV_CONFIG_PATH, DEV_DIR  # noqa: PLC0415

    if DEV_DIR.exists():
        ctx.run(["rm", "-rf", str(DEV_DIR)])

    if DEV_CONFIG_PATH.exists():
        ctx.run(["rm", str(DEV_CONFIG_PATH)])


@duty(pre=[dev_clean])
def dev_setup(ctx: Context) -> None:
    """Provision a mock development environment."""
    # We import these here to avoid importing code before pytest-cov is initialized
    from neatfile.constants import DEFAULT_CONFIG_PATH, DEV_CONFIG_PATH, DEV_DIR  # noqa: PLC0415

    ctx.run(["mkdir", "-p", str(DEV_DIR)])
    ctx.run(["cp", str(DEFAULT_CONFIG_PATH), str(DEV_CONFIG_PATH)])

    # Create projects
    projects = [
        DEV_DIR / "projects" / "project1",
        DEV_DIR / "projects" / "project2",
    ]
    for project in projects:
        ctx.run(["mkdir", "-p", str(project)])
        subdirs = [
            project / "foo",
            project / "bar",
            project / "baz",
        ]
        for subdir in subdirs:
            ctx.run(["mkdir", "-p", str(subdir)])
            while len(list(subdir.iterdir())) < 11:  # noqa: PLR2004
                subsubdir = subdir / f"{random.choice(NOUNS)}_{random.choice(NOUNS)}"
                if not subsubdir.exists():
                    ctx.run(["mkdir", "-p", str(subsubdir)])

    # Add projects to dev-config.toml
    with DEV_CONFIG_PATH.open("a") as f:
        for project in projects:
            f.write(f"\n[projects.{project.name}]\n")
            f.write(f'    name = "{project.name}"\n')
            f.write(f'    path = "{project}"\n')

    # Create test files
    test_file_dir = DEV_DIR / "files"
    ctx.run(["mkdir", "-p", str(test_file_dir)])
    while len(list(test_file_dir.iterdir())) < 11:  # noqa: PLR2004
        test_file = test_file_dir / f"{random.choice(NOUNS)}_{random.choice(NOUNS)}.txt"
        ctx.run(["touch", str(test_file)])
