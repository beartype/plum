import builtins
import inspect
import typing

import pytest
from rich.text import Text

from .util import rich_render
from plum.repr import _repr_mimebundle_from_rich_, _safe_getfile, repr_type


class A:
    pass


def test_repr_type():
    assert rich_render(repr_type(int)).strip() == "int"
    assert rich_render(repr_type(A)).strip() == "tests.test_repr.A"
    assert rich_render(repr_type(typing)).strip() == "typing"


def test_repr_mimebundle_from_rich():
    class A:
        def __rich_console__(self, console, options):
            yield Text("rendering")

    for v in _repr_mimebundle_from_rich_(A(), [], []).values():
        assert "rendering" in v
    assert _repr_mimebundle_from_rich_(A(), ["text/plain"], []).keys() == {"text/plain"}
    assert _repr_mimebundle_from_rich_(A(), [], ["text/plain"]).keys() == {"text/html"}


def test_safe_getfile(monkeypatch):
    assert _safe_getfile(A) == inspect.getfile(A)
    with pytest.raises(OSError, match="(?i)source code not available"):
        _safe_getfile(int)
    # This is a little dangerous, but it seems to work OK.
    monkeypatch.setattr(builtins, "__file__", "/path/to/file", raising=False)
    assert _safe_getfile(int) == "/path/to/file"
