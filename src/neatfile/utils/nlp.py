"""Natural language processing utilities."""

import cappa
import spacy

from .pretty_print import pp

try:
    nlp = spacy.load("en_core_web_md")
except OSError as e:
    pp.rule("Downloading spaCy model...")
    spacy.cli.download("en_core_web_md")  # type: ignore [attr-defined]
    pp.rule()
    pp.info(":rocket: Model downloaded successfully. Run `neatfile` again.")
    raise cappa.Exit() from e
