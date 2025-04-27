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
CI = os.environ.get("CI", "0") in {"1", "true", "yes", ""}


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


@duty(silent=True, post=["dev_clean"])
def clean(ctx: Context) -> None:
    """Clean the project."""
    ctx.run("rm -rf .cache")
    ctx.run("rm -rf .reports")
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
def mypy(ctx: Context) -> None:
    """Check the code with mypy."""
    os.environ["FORCE_COLOR"] = "1"
    ctx.run(
        tools.mypy("src/", config_file="pyproject.toml"),
        title=pyprefix("mypy check"),
        command="mypy --config-file pyproject.toml src/",
    )


@duty
def typos(ctx: Context) -> None:
    """Check the code with typos."""
    ctx.run(
        ["typos", "--config", ".typos.toml"],
        title=pyprefix("typos check"),
        command="typos --config .typos.toml",
    )


@duty(skip_if=CI, skip_reason="skip pre-commit in CI environments")
def precommit(ctx: Context) -> None:
    """Run pre-commit hooks."""
    ctx.run(
        "SKIP=mypy,pytest,ruff pre-commit run --all-files",
        title=pyprefix("pre-commit hooks"),
    )


@duty(pre=[ruff, mypy, typos, precommit], capture=CI)
def lint(ctx: Context) -> None:
    """Run all linting duties."""


@duty(capture=CI)
def update(ctx: Context) -> None:
    """Update the project."""
    ctx.run(["uv", "lock", "--upgrade"], title="update uv lock")
    ctx.run(["pre-commit", "autoupdate"], title="pre-commit autoupdate")
    ctx.run(
        ["uv", "pip", "compile", "-q", "pyproject.toml", "-o", "requirements.txt"],
        title="update requirements.txt",
    )


@duty
def download_spacy_model(ctx: Context) -> None:
    """Download the spaCy model."""
    output = ctx.run(
        "pip list | grep 'en_core_web_md' || echo 'not installed' ",
        title="check en_core_web_md",
    )
    if "not installed" in output:
        ctx.run(
            ["uv", "run", "spacy", "download", "en_core_web_md"],
            title="download en_core_web_md",
        )


@duty(pre=[download_spacy_model])
def test(ctx: Context, *cli_args: str) -> None:
    """Test package and generate coverage reports."""
    ctx.run(
        tools.pytest(
            "tests",
            "src",
            config_file="pyproject.toml",
            color="yes",
        ).add_args(
            "--cov",
            "--cov-config=pyproject.toml",
            "--cov-report=xml",
            "--cov-report=term",
            *cli_args,
        ),
        title=pyprefix("Running tests"),
        capture=CI,
    )


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
