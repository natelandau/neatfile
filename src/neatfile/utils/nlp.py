"""Natural language processing utilities."""

import subprocess  # noqa: S404
import sys

import cappa
import spacy
from nclutils import pp

try:
    nlp = spacy.load("en_core_web_md")
except OSError as e:
    python = str(sys.executable)
    pp.rule("Downloading spaCy model...")
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_md"], check=False)  # noqa: S603
    pp.rule()
    pp.info(":rocket: Model downloaded successfully. Run `neatfile` again.")
    raise cappa.Exit() from e
