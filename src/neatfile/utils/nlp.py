"""Natural language processing utilities."""

import subprocess  # noqa: S404

import cappa
import spacy

from .pretty_print import pp

try:
    nlp = spacy.load("en_core_web_md")
except OSError as e:
    pp.rule("Downloading spaCy model...")
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_md"], check=False)  # noqa: S607
    pp.rule()
    pp.info(":rocket: Model downloaded successfully. Run `neatfile` again.")
    raise cappa.Exit() from e
