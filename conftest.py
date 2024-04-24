"""Doctest configuration."""

from doctest import ELLIPSIS, NORMALIZE_WHITESPACE

import pytest
from sybil import Sybil
from sybil.parsers.myst import DocTestDirectiveParser as MarkdownDocTestParser
from sybil.parsers.myst import PythonCodeBlockParser as MarkdownPythonCodeBlockParser
from sybil.parsers.myst import SkipParser as MarkdownSkipParser
from sybil.parsers.rest import DocTestParser as ReSTDocTestParser
from sybil.parsers.rest import PythonCodeBlockParser as ReSTPythonCodeBlockParser
from sybil.parsers.rest import SkipParser as ReSTSkipParser

OPTIONS = ELLIPSIS | NORMALIZE_WHITESPACE


@pytest.fixture(scope="module")
def use_clean_dispatcher():
    import plum

    # Save the original dispatcher.
    dispatcher = plum.dispatch
    # Swap the dispatcher with a temporary one.
    temp_dispatcher = plum.Dispatcher()
    plum.dispatch = temp_dispatcher
    yield
    # Restore the original dispatcher.
    plum.dispatch = dispatcher


markdown_examples = Sybil(
    parsers=[
        MarkdownDocTestParser(optionflags=OPTIONS),
        MarkdownPythonCodeBlockParser(doctest_optionflags=OPTIONS),
        MarkdownSkipParser(),
    ],
    patterns=["*.md"],
    fixtures=["use_clean_dispatcher"],
)

rest_examples = Sybil(
    parsers=[
        ReSTDocTestParser(optionflags=OPTIONS),
        ReSTPythonCodeBlockParser(),
        ReSTSkipParser(),
    ],
    patterns=["*.py"],
)

pytest_collect_file = (markdown_examples + rest_examples).pytest()
