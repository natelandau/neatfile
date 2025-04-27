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
6. Install pre-commit hooks: `pre-commit install --install-hooks`

Confirm your setup by running `which neatfile`. The output should reference your virtual environment (e.g., `/Users/your-username/neatfile/.venv/bin/neatfile`).

### Running Tasks

We use [Duty](https://pawamoy.github.io/duty/) as our task runner. Common tasks:

-   `duty --list` - List all available tasks
-   `duty lint` - Run all linters
-   `duty test` - Run all tests

## Manual Testing Environment

To create a ready-made testing environment:

1. Run `duty dev-setup`
2. This creates a `.development/` directory in your home folder with:
    - `dev-config.toml` - Test configuration file
    - `projects/` - Example project directories
    - `files/` - Example files for testing

Test the CLI with commands like:

```bash
neatfile --project project1 --subdir .development/files/*.txt
```

## Development Guidelines

When developing for neatfile, please follow these guidelines:

-   Write full docstrings
-   All code should use type hints
-   Write unit tests for all new functions
-   Write integration tests for all new features
-   Follow the existing code style

## Commit Process

1. Create a branch for your feature or fix
2. Make your changes
3. Ensure code passes linting with `duty lint`
4. Ensure tests pass with `duty test`
5. Commit using [Commitizen](https://github.com/commitizen-tools/commitizen): `cz c`
6. Push your branch and create a pull request

We use [Semantic Versioning](https://semver.org/) for version management.
