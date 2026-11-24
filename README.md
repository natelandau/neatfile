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
-   Remove filler words such as "the", "of", and "and"
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

### Undo

-   Revert the last run of `clean`, `sort`, or `process` with `neatfile undo`

## Installation

neatfile requires Python 3.12 or later.

```bash
# With uv
uv tool install neatfile

# With pip
python -m pip install --user neatfile
```

> [!NOTE]\
> The first time you run `neatfile sort`, it downloads a ~30 MB word-embedding model (`potion-base-8M`) used to match terms in filenames against directory names. The model is stored in `$XDG_DATA_HOME/neatfile/models` (default `~/.local/share/neatfile/models`) and is reused by every later run, including after upgrades. Set `NEATFILE_MODEL_DIR` to store it elsewhere.

## Quickstart

neatfile has six subcommands:

-   `clean` - Clean and normalize filenames
-   `config` - View the user configuration file (or create one)
-   `sort` - Move files into a directory tree
-   `process` - Clean AND sort files
-   `tree` - Print the project folders that `sort` can move files into. Folders with a `.neatfileignore` file show the label `(ignored)`.
-   `undo` - Revert the last run of `clean`, `sort`, or `process`

To see the help text for a subcommand, run `neatfile <subcommand> --help`.

### Example usage

Copy the default configuration file into place for you to edit:

```console
$ neatfile config --create
✅ Success: User config file created: ~/.config/neatfile/config.toml
```

Clean all text files in a directory (with `split_words = true` in the config file)

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

Values are set in the following order of precedence, highest first:

1. CLI flags
2. Environment variables
3. Configuration files, in this order: the project section, the development file, the user file, then the default values in the sample configuration file below.

### Environment variables

Set any top-level key from the sample configuration file with the variable `NEATFILE_KEY`, where `KEY` is the key name in uppercase. For example, `NEATFILE_SEPARATOR` sets `separator`.

neatfile reads each value as plain text, without quotes. A boolean key accepts `true` or `false` in any case. A key with named values, such as `separator`, accepts the name in any case. Write a list as a TOML array, for example `NEATFILE_STOPWORDS='["draft", "final"]'`. A list from an environment variable replaces the global list from the configuration files, and an empty array (`[]`) clears it. Keys inside a `[projects.NAME]` section have no environment variable. neatfile ignores variables that do not name a key.

```bash
NEATFILE_SEPARATOR=underscore neatfile clean report.pdf
```

If a value has the wrong type, neatfile prints the key, the source, the value, and the allowed values, then exits with code 1. A boolean in a file must be a TOML boolean, and a list must be a list of strings.

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

# Extra words to remove from filenames, in addition to the built-in filler words
stopwords          = []

# Remove filler words such as "the", "of", and "and" from filenames.
# Words in match_case_list are never removed, and IT, US, OR, IN, ON,
# AT, ME, and AS are kept when written in capitals, even if listed in stopwords.
# true or false
strip_stopwords    = true

# Transform the case of the filename.
# Options: "ignore", "lower", "upper", "title", "sentence"
transform_case     = "ignore"

# Time zone for the date that neatfile reads from the file creation time.
# Use an IANA time zone name. If you do not set it, neatfile uses the local time zone.
# tz                 = "America/New_York"

# Number of recent runs that `undo` can reverse. Each run that renames or
# moves files counts as one. Set to 0 to turn the undo journal off.
# Only the top level of the configuration file can set this.
undo_history_runs  = 50

# Extra terms that `sort` and `process` use to match files to folders.
# A project section can set its own user_terms.
# A later layer replaces this list. `--term` flags replace the configured terms.
user_terms         = []

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
        # `stopwords`, `ignored_files`, and `match_case_list` in a project combine with the global lists.
        # Every other key replaces the global value.
        # For example: user_terms = ["legal", "invoice"]
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

## Undo

neatfile records each file that `clean`, `sort`, and `process` rename or move. The `neatfile undo` command moves the files of the most recent run back to their original paths. Each later `neatfile undo` reverts the run before it.

```bash
# Show the files of the last run and ask before restoring them
neatfile undo

# Restore without asking
neatfile undo --force

# Show what undo will do and change nothing
neatfile undo -n
```

`neatfile undo` always asks for confirmation, even when you did not use `--confirm` for the run. If a run replaced an existing file and kept a backup, undo also moves the backup back to its original name.

Undo never overwrites or deletes a file. It skips a file and reports the reason in these cases:

-   Another file has the original name. The file stays in the journal. Move the other file away, then run `neatfile undo` again.
-   The folder of the renamed file does not exist, for example because it is on a drive that is not connected. The file stays in the journal. Connect the drive, then run `neatfile undo` again.
-   The renamed file is not at its new path, but its folder exists. The file moved after the run, so undo cannot find it. Undo removes the file from the journal.

If the run kept a backup of a file that it replaced, undo moves the backup back to that path, also when it cannot find the renamed file. If another file already has that path, the backup stays where it is and undo shows the backup path.

If undo skips a file or removes it from the journal, the command exits with code 1. The next `neatfile undo` finishes the skipped files of that run before it reverts an older run.

The journal is at `$XDG_STATE_HOME/neatfile/undo-journal.jsonl`. If `XDG_STATE_HOME` is not set, the journal is at `~/.local/state/neatfile/undo-journal.jsonl`. The `undo_history_runs` setting sets how many runs the journal keeps. If the journal has a line that neatfile cannot read, undo shows the line number. The next change to the journal removes that line. An undo and a run that renames or moves files both change the journal.

## Caveats

`neatfile` is built for my own personal use. While this cli is thoroughly tested, I make no warranties for any data loss or other issuesthat may result from use. I strongly recommend running in `--dry-run` mode prior to committing changes.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for more information.
