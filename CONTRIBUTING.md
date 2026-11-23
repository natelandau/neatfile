# Contributing to neatfile

Thank you for your interest in contributing to neatfile! This document provides guidelines and instructions to make the contribution process smooth and effective.

## Types of Contributions Welcome

-   Bug fixes
-   Feature enhancements
-   Documentation improvements
-   Test additions

## Development Setup

### Prerequisites

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. To start developing:

1. Install uv using the [recommended method](https://docs.astral.sh/uv/installation/) for your operating system
2. Clone this repository: `git clone https://github.com/natelandau/neatfile`
3. Navigate to the repository: `cd neatfile`
4. Install dependencies with uv: `uv sync`
5. Activate your virtual environment: `source .venv/bin/activate`
6. Install the git hooks with [prek](https://prek.j178.dev/): `prek install --prepare-hooks`

To make sure that the setup works, run `which neatfile`. The output must show a path in your virtual environment, for example `/Users/USERNAME/neatfile/.venv/bin/neatfile`.

### Running Tasks

We use [Duty](https://pawamoy.github.io/duty/) as our task runner. Common tasks:

-   `duty --list` - List all available tasks
-   `duty lint` - Run all linters, including the format check
-   `duty test` - Run all tests

Run checks with `duty`, not with `pytest`, `ruff`, `ty`, `typos`, or `prek` directly. The `duty` tasks skip a check that already passed on the same files and print `already passed on`. That message means that the check passed. If you add pytest arguments, for example `duty test -k NAME`, the tests always run.

## Manual Testing Environment

Use a sandbox to try the CLI without changes to your real files. Run `duty dev-setup` to create a `.development/` directory in the repository root. Git ignores this directory. It contains:

-   `dev-config.toml` - Test configuration file. The CLI loads it automatically when you run neatfile from this repository.
-   `projects/` - Example project directories, `project1` and `project2`
-   `files/` - Example files for testing

Try the CLI against the sandbox files. The `--dry-run` flag shows the changes without moving or renaming files:

```bash
neatfile clean --dry-run .development/files/*.txt
neatfile process --project project1 .development/files/*.txt
```

The `process` command asks you to select a folder, so you must run it in an interactive terminal.

To delete the sandbox, run `duty dev-clean`.

## Development Guidelines

Obey these guidelines when you write code for neatfile:

-   Write full docstrings
-   Add type hints to all code
-   Write unit tests for all new functions
-   Write integration tests for all new features
-   Follow the existing code style

## Commit Process

1. Create a branch for your feature or fix
2. Make your changes
3. Make sure that `duty lint` passes
4. Make sure that `duty test` passes
5. Commit using [Commitizen](https://github.com/commitizen-tools/commitizen): `cz c`
6. Push your branch and create a pull request

We use [Semantic Versioning](https://semver.org/) for version management.
