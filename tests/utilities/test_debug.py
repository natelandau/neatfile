"""Tests for the debug function."""

import os
import re

from neatfile.views import print_debug


def test_print_debug(clean_stdout, debug) -> None:
    """Verify print_debug outputs basic debug info."""
    # Given: No arguments

    # When: Calling print_debug with no arguments
    print_debug()
    output = clean_stdout()

    # Then: Output contains expected debug sections and formatting
    assert "debug info" in output
    regexes = [
        r"^System: .*$",
        r"^Python: .* (.*)$",
    ]
    for regex in regexes:
        assert re.search(regex, output, re.MULTILINE)

    assert "Environment variables:" not in output
    assert "Installed packages:" not in output


def test_print_debug_custom(clean_stdout, debug) -> None:
    """Verify print_debug handles custom debug sections."""
    # Given: Custom debug dictionaries
    config_as_dict = {
        "Configuration": {
            "key": "value",
            "key2": "value2",
            "key3": "value3",
        }
    }

    cli_args_as_dict = {
        "CLI Flags": {
            "flag1": "value1",
            "flag2": "value2",
            "flag3": "value3",
        }
    }

    single_variables = {
        "key": "value",
        "key2": "value2",
        "key3": "value3",
    }

    # When: Calling print_debug with custom sections
    print_debug(custom=[config_as_dict, cli_args_as_dict, single_variables])
    output = clean_stdout()

    # debug(output)

    # Then: Output contains standard and custom debug sections
    assert "debug info" in output
    regexes = [
        r"^System: .*$",
        r"^Python: .*\s+(.*)$",
        r"^Configuration:$",
        r"^ +key +value +$",
        r"^ +key2 +value2 +$",
        r"^ +key3 +value3 +$",
        r"^CLI Flags:$",
        r"^ +flag1 +value1 +$",
        r"^ +flag2 +value2 +$",
        r"^ +flag3 +value3 +$",
        r"^key: +value +$",
        r"^key2: +value2 +$",
        r"^key3: +value3 +$",
    ]
    for regex in regexes:
        assert re.search(regex, output, re.MULTILINE)

    assert "Environment variables:" not in output
    assert "Installed packages:" not in output


def test_print_debug_envars(clean_stdout, debug) -> None:
    """Verify print_debug filters environment variables by prefix."""
    # Given: An environment variable with the target prefix
    os.environ["SCRIPTUTILITIES_TEST_KEY"] = "test_value"

    # When: Calling print_debug with an environment variable prefix
    print_debug(envar_prefix="SCRIPTUTILITIES_")
    output = clean_stdout()

    # Then: Output includes filtered environment variables
    assert "debug info" in output
    regexes = [
        r"^System: .*$",
        r"^Python: .* (.*)$",
        r"^Environment variables:$",
        r"^ +SCRIPTUTILITIES_TEST_KEY +test_value",
    ]
    for regex in regexes:
        assert re.search(regex, output, re.MULTILINE)

    assert "Installed packages:" not in output


def test_print_debug_all_packages(clean_stdout, debug) -> None:
    """Verify print_debug includes all installed packages."""
    # Given: No arguments

    # When: Calling print_debug with no arguments
    print_debug(all_packages=True)
    output = clean_stdout()

    # debug(output)

    # Then: Output includes all installed packages
    regexes = [
        r"^System: .*$",
        r"^Python: .* (.*)$",
        r"^Installed packages:$",
        r"^ +rich +\d{1,3}\.\d{1,3}\.\d{1,3} +$",
        r"^ +questionary +\d{1,3}\.\d{1,3}\.\d{1,3} +$",
    ]
    for regex in regexes:
        assert re.search(regex, output, re.MULTILINE)

    assert "Environment variables:" not in output


def test_print_debug_specific_packages(clean_stdout, debug) -> None:
    """Verify print_debug includes specific installed packages."""
    # Given: No arguments

    # When: Calling print_debug with no arguments
    print_debug(packages=["rich"])
    output = clean_stdout()

    # debug(output)

    # Then: Output includes all installed packages
    regexes = [
        r"^System: .*$",
        r"^Python: .* (.*)$",
        r"^Installed packages:$",
        r"^ +rich +\d{1,3}\.\d{1,3}\.\d{1,3} +$",
    ]
    for regex in regexes:
        assert re.search(regex, output, re.MULTILINE)

    assert "Environment variables:" not in output
    assert "questionary" not in output
