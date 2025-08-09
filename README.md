[![PyPI version](https://badge.fury.io/py/neatfile.svg)](https://badge.fury.io/py/neatfile) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/neatfile) [![Tests](https://github.com/natelandau/neatfile/actions/workflows/test.yml/badge.svg)](https://github.com/natelandau/neatfile/actions/workflows/test.yml) [![codecov](https://codecov.io/gh/natelandau/neatfile/graph/badge.svg?token=Y11Z883PMI)](https://codecov.io/gh/natelandau/neatfile)

# neatfile

CLI to normalize and organize your files based on customizable rules.

## Why build this?

I have filesystem OCD. Maybe you share my annoyance at having files with non-normalized filenames sent from coworkers, friends, and family. On any given day, I receive dozens of files via Slack, email, and other messaging apps sent by people who have their own way of naming files. For example:

-   `department 2023 financials and budget 08232002.xlsx`
-   `some contract Jan7 reviewed NOT FINAL (NL comments) v13.docx`
-   `John&Jane-meeting-notes 4 3 25.txt`
-   `Project_mockups(WIP)___sep92022.pdf`
-   `FIRSTNAMElastname Resume (#1) [companyname].PDF`

What's the problem here?

-   No self-evident way to organize them into folders
-   No common patterns to search for
-   Dates all over the place or nonexistent
-   Inconsistent casing and word separators
-   Special characters within text
-   I could go on and on...

`neatfile` is created to solve for these problems by providing an easy CLI to rename and organize files into directories based on your preferences.

## Features

### Filename cleaning and normalization

-   Remove special characters
-   Trim multiple separators (`word----word` becomes `word-word`)
-   Normalize filenamesto `lowercase`, `uppercase`, `Sentence case`, or `Title Case`
-   Normalize all files to a common word separator (`_`, `-`, ` `, `.`)
-   Enforce lowercase file extensions
-   Remove common English stopwords
-   Split `camelCase` words into separate words (`camel Case`)

### Date parsing

-   Identify dates in filenames in many different formats and and normalize them into a preferred format
-   Add the date to the beginning or the end of the filename (or remove it entirely)
-   Fall back to file creation date if no date is found in the filename

### File organization

-   Define projects with directory trees in the config file
-   Match terms in filenames to folder names and move files into matching folder
-   Use vector matching to find similar terms
-   Respect the [Johnny Decimal](https://johnnydecimal.com) system, if you use it
-   Optionally, add `.neatfile` files to directories containing a list of words that will match files
-   Add a `.neatfileignore` file to directories to exclude that directory from being matched to a project. This will not exclude children of the directory.

## Installation

neatfile requires python 3.11 or higher.

```bash
# With uv
uv tool install neatfile

# With pip
python -m pip install --user neatfile
```

> [!NOTE]\
>  A ~35mb language model will be downloaded on first run to provide vector matching between filenames and directory names.

## Quickstart

neatfile has four subcommands:

-   `clean` - Clean and normalize filenames
-   `config` - View the user configuration file (or create one)
-   `sort` - Move files into a directory tree
-   `process` - Clean AND sort files
-   `tree` - Print a tree representation of a project's directory structure

To see the help text for a subcommand, run `neatfile <subcommand> --help`.

### Example usage

Copy the default configuration file into place for you to edit:

```console
$ neatfile config --create
✅ Success: User config file created: ~/.config/neatfile/config.toml
```

Clean all text files in a directory

```console
$ neatfile clean *.txt
✅ Success: CamelCase_with_underscore_separators.txt -> 2025-04-16 Camel Case Underscore Separators.txt
✅ Success: datestamped sept 04 2023 (signed).txt -> 2023-09-04 Datestamped Signed.txt
✅ Success: removing.special.characters.$#@.08-05-2024.txt -> 2024-08-05 Removing Special Characters.txt
```

Sort a file into a specific directory within a project (without cleaning the filename)

```console
$ neatfile sort --project=work 20230904_datestamped_signed.txt
✅ Success: 20230904_datestamped_signed.txt -> ~/work/administrative/legal/20230904_datestamped_signed.txt
```

Process a file to clean and sort it

```console
$ neatfile process --project=work --date-format=%Y-%m-%d datestamped_20230904_signed.txt
✅ Success: datestamped_20230904_signed.txt -> ~/work/administrative/legal/2023-09-04 Datestamped Signed.txt
```

## Configuration

Define personalized defaults in a configuration file and apply them consistently across all runs.

To create a configuration file. Run `neatfile config --create` to create a configuration file at `~/.config/neatfile/config.toml` or your `$XDG_CONFIG_HOME/neatfile/config.toml` if set.

Preferences can also be set on a per project basis within the configuration file.

Values are set in the following order of precedence:

1. CLI arguments
2. Project specific settings within the configuration file
3. Default values in the user configuration file
4. Default values as specified below in the sample configuration file.

### Sample configuration file

```toml
# Global settings
# Override on a per project basis in the [projects] section if needed.

# How to interpret ambiguous date formats such as 03-04-12.
# Defaults to US format with month first.
# options "day", "month", "year"
date_first = "month"

# date format
# If specified, the date will be added to the filename following this format.
# See https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes for details on how to specify a format.
date_format        = ""

# Ignores dotfiles (files that start with a period) when cleaning a directory.
# true or false
ignore_dotfiles    = true

# File names matching this regex will be ignored
ignore_file_regex  = ''

# List of file names to ignore
# Useful if there are consistently recurring files that you don't want to clean.
ignored_files      = []

# Where to insert the date.
# "before" or "after"
insert_location    = "before"

# Force the casing of certain words.
# Useful for acronyms or proper nouns such as 'iMac', 'CEO', or 'John'
match_case_list    = []

# Overwrite existing files. true or false.
# If false, a backup of the original file will be created before a new file is written.
overwrite_existing = false

# Separator to use between words.
# Options: "ignore", "underscore", "space", "dash".
# "ignore" does it's best to keep the original separator.
separator          = "ignore"

# Split CamelCase words into separate words.
# true or false
split_words        = false

# List of specific stopwords to be stripped from filenames in
# addition to the default English stopwords
stopwords          = []

# Strip stopwords from filenames.
# true or false
strip_stopwords    = true

# Transform the case of the filename.
# Options: "ignore", "lower", "upper", "title", "sentence"
transform_case     = "ignore"

# Override the global settings for specific projects and tell neatfile
# how to organize files into a directory tree.
[projects]
    [projects.project_name]
        # The name of the project is used as a command line option. (e.g. --project=project_name)
        name = ""

        # The path to the project's directory
        path = ""

        # The type of project.
        # Options: "jd" for Johnny Decimal, "folder" for a folder structure
        type = "folder"

        # The depth of folders to index beneath the project's root path
        depth = 2

        # Default configuration values specified above can be overridden here on a per project basis
```

## Directory Matching

neatfile uses smart matching to determine which directory a file belongs in:

1. **Word Extraction**: Words are extracted from your filename and compared with directory names in your project structure.
2. **Intelligent Matching**: The system uses both exact matches and vector similarity to find the best directory. For example, a file containing "budget" might match with a "Finance" directory through vector similarity.
3. **Hierarchical Navigation**: neatfile considers your project's directory tree (up to the configured depth) when finding directories to match files to.
4. **Ignoring Folders**: If a folder contains a `.neatfileignore` file, it will be ignored when matching files to directories but it's children will still be considered.

### Customizing Match Behavior

You can influence how files match to directories in two ways:

1. **Using `--term` Flags**: Specify additional matching terms when running a command:

    ```bash
    neatfile sort --project=work --term=legal contract.pdf
    ```

    This tells neatfile to include directories that match "legal" when sorting the file even though it doesn't contain the term "legal" in the filename.

1. **Creating `.neatfile` Files**: Add a .neatfile text file to any directory containing additional terms that should match to that location:

    ```bash
    # /path/to/work/admin/legal/.neatfile
    contract
    agreement
    nda
    ```

    Now any file containing these terms will preferentially match to the legal directory.

### Example Scenario

With a project structure like:

```shell
work/
├── admin/
│   ├── hr/
│   │   └── .neatfile # Contains the term "handbook"
│   └── legal/
├── finance/
│   ├── budgets/
│   └── invoices/
├── ignore-me/
│   └── .neatfileignore # Ignore this directory
└── marketing/
    ├── campaigns/
    └── social-media/
```

Configured in config.toml:

```toml
[projects.work]
name = "work"
path = "/path/to/work"
depth = 2
```

neatfile would automatically:

-   Move `2023_employee_handbook.pdf` to the `hr` directory
-   Sort `Q2_budget_forecast.xlsx` into the `budgets` directory
-   Place `new_campaign_assets.zip` in the `campaigns` directory

### Vector matching

Behind the scenes, neatfile uses a language model to find similar terms in a filename and a directory name by comparing their vector embeddings. This is useful for matching terms that are similar but not exactly the same. For example, this will match the term `mockups` with the directory name `mockup` or the term `budget` with the term `finance`.

## Caveats

`neatfile` is built for my own personal use. While this cli is thoroughly tested, I make no warranties for any data loss or other issuesthat may result from use. I strongly recommend running in `--dry-run` mode prior to committing changes.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for more information.
